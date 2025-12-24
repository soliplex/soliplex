import json

import requests
import textual
from ag_ui import core as agui_core
from textual import app as t_app
from textual import binding as t_binding
from textual import containers as t_containers
from textual import reactive as t_reactive
from textual import screen as t_screen
from textual import widget as t_widget
from textual import widgets as t_widgets

from soliplex.agui import parser as agui_parser


class RunMetadataView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Return"),
    ]

    def __init__(self, run_id: str, label_text: str, *args, **kwargs):
        self.run_id = run_id
        self.label_text = label_text
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        yield t_widgets.Label(f"Run: {self.run_id}")

        with t_containers.Grid():
            yield t_widgets.Label("Run Label")
            yield t_widgets.Input(self.label_text)

        yield t_widgets.Footer()

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        event.input.clear()
        self.dismiss(event.value)


class RunLabeledWidget(t_widget.Widget):
    DEFAULT_CSS = """
    RunLabeledWidget {
        layout: horizontal;
        height: auto;
    }
    """


class RunMessageWidget(t_widget.Widget):
    DEFAULT_CSS = """
    RunMessageWidget {
        layout: horizontal;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, message_info, *args, **kwargs):
        self.message_info = message_info
        super().__init__()

    @property
    def message_role(self):
        return self.message_info["role"]

    @property
    def message_content(self):
        content = self.message_info.get("content")

        if self.message_role == "user":
            if not isinstance(content, str):
                if content.type == "binary":
                    content = "<binary>"
                else:
                    content = content.text

        return str(content) if content is not None else None

    def compose(self) -> t_app.ComposeResult:
        role = self.message_role
        content = self.message_content

        yield t_widgets.Label(f"{role.capitalize()}:")

        if content is not None:
            yield t_widgets.Static(content)


class RunEventWidget(t_widget.Widget):
    DEFAULT_CSS = """
    RunEventWidget {
        layout: horizontal;
        height: auto;
        padding: 1;
    }
    """

    def __init__(self, event_info, *args, **kwargs):
        self.event_info = event_info
        super().__init__()

    @property
    def event_type(self):
        return self.event_info["type"]

    @property
    def event_content(self):
        info = self.event_info
        if self.event_type == "STATE_SNAPSHOT":
            content = "*state snapshot*"
        elif self.event_type == "STATE_DELTA":
            content = "*state delta*"
        elif "delta" in info:
            content = info["delta"]
        elif "content" in info:
            content = str(info["content"])
        else:
            content = ""

        return content

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Label(self.event_type)
        yield t_widgets.Static(self.event_content)


class RunView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Return"),
        t_binding.Binding("ctrl+l", "edit_label", "Label"),
    ]
    DEFAULT_CSS = """
    RunView Label {
        width: 12;
        text-align: right;
    }
    RunView Static {
        width: 1fr;
        text-align: left;
    }
    #run-messages {
        height: 10;
    }
    #run-events {
    }
    #run-usage {
        height: 10;
    }
    """

    def __init__(self, room_id, thread_id, run_id, *args, **kwargs):
        self.room_id = room_id
        self.thread_id = thread_id
        self.run_id = run_id
        self._run_info = None
        super().__init__()

    @property
    def run_info(self) -> dict[str, dict]:
        if self._run_info is None:
            info = requests.get(
                f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}/agui/"
                f"{self.thread_id}/{self.run_id}",
            ).json()
            self._run_info = info

        return self._run_info

    @property
    def run_events(self) -> list[dict]:
        return self.run_info["events"]

    @property
    def run_messages(self) -> dict[str, dict]:
        return self.run_info["run_input"]["messages"]

    @property
    def run_meta(self) -> dict[str, str]:
        return self.run_info["metadata"]

    @property
    def run_usage(self) -> dict[str, int]:
        return self.run_info["usage"]

    @property
    def label_text(self) -> dict[str, dict]:
        meta = self.run_meta
        return meta["label"] if meta else "<no label>"

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        with RunLabeledWidget():
            yield t_widgets.Label("Run:")
            yield t_widgets.Static(self.run_id)

        with RunLabeledWidget():
            yield t_widgets.Label("Label:")
            yield t_widgets.Static(self.label_text, id="run-label")

        with RunLabeledWidget():
            yield t_widgets.Label("Messages:")

        with t_containers.VerticalScroll(id="run-messages"):
            for message in self.run_messages:
                with RunLabeledWidget():
                    yield RunMessageWidget(message)

        with RunLabeledWidget():
            yield t_widgets.Label("Events:")

        with t_containers.VerticalScroll(id="run-events"):
            for event in self.run_events:
                with RunLabeledWidget():
                    yield RunEventWidget(event)

        usage = self.run_usage

        if usage is not None:
            with RunLabeledWidget():
                yield t_widgets.Label("Usage:")

            for key, value in usage.items():
                with RunLabeledWidget():
                    yield t_widgets.Label(f"- {key}")
                    yield t_widgets.Static(str(value))

        yield t_widgets.Footer()

    @textual.work
    async def action_edit_label(self) -> None:
        rmv = RunMetadataView(self.run_id, self.label_text)
        found = await self.app.push_screen_wait(rmv)

        if found is not None:
            found = found.strip()

            payload = {"label": found} if found else {}

            requests.post(
                f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}/agui/"
                f"{self.thread_id}/{self.run_id}/meta",
                json=payload,
            )

            self._run_info["metadata"] = payload
            self.query_one("#run-label").content = self.label_text


class RunButtonWidget(t_widget.Widget):
    DEFAULT_CSS = """
    RunButtonWidget {
        layout: horizontal;
        height: auto;
    }
    """


class ThreadRunsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Return"),
    ]
    DEFAULT_CSS = """
    .run-label {
        padding: 1;
    }
    """

    def __init__(self, room_id, thread_id, *args, **kwargs):
        self.room_id = room_id
        self.thread_id = thread_id
        self._runs = None
        super().__init__()

    @property
    def runs(self) -> dict[str, dict]:
        if self._runs is None:
            info = requests.get(
                f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}/agui/"
                f"{self.thread_id}",
            ).json()
            self._runs = info["runs"]

        return self._runs

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        yield t_widgets.Label(f"Runs in thread: {self.thread_id}")

        with t_containers.VerticalScroll(id="runs-list"):
            for run_id, run_info in self.runs.items():
                with RunButtonWidget():
                    yield t_widgets.Button(
                        name=run_id,
                        label=f"{run_id}",
                    )

                    if run_info["metadata"] is not None:
                        yield t_widgets.Label(
                            run_info["metadata"]["label"],
                            classes="run-label",
                        )

        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        run_id = event.button.name
        event.stop()
        run_view = RunView(self.room_id, self.thread_id, run_id)
        self.app.push_screen(run_view)


class ThreadButtonWidget(t_widget.Widget):
    DEFAULT_CSS = """
    ThreadButtonWidget {
        layout: horizontal;
        height: auto;
    }
    """


class RoomThreadsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding(
            "escape",
            "dismiss(None)",
            "Return to room",
        ),
    ]
    DEFAULT_CSS = """
    .thread-name {
        padding: 1;
    }
    """

    def __init__(self, room_id, *args, **kwargs):
        self.room_id = room_id
        self._threads = None
        super().__init__()

    @property
    def threads(self) -> dict[str, dict]:
        if self._threads is None:
            info = requests.get(
                f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}/agui",
            ).json()
            self._threads = info["threads"]
            self._threads_by_id = {
                thread_info["thread_id"]: thread_info
                for thread_info in self._threads
            }

        return self._threads

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        threads = self.threads

        if threads:
            yield t_widgets.Label(f"Threads in room: {self.room_id}")
        else:
            yield t_widgets.Label(f"No threads in room: {self.room_id}")

        with t_containers.VerticalScroll(id="threads-list"):
            for thread_info in self.threads:
                thread_id = thread_info["thread_id"]
                meta = thread_info.get("metadata")
                with ThreadButtonWidget():
                    yield t_widgets.Button(
                        name=thread_id,
                        label=f"{thread_id}",
                    )
                    if meta is not None:
                        yield t_widgets.Label(
                            meta["name"],
                            classes="thread-name",
                        )

        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        thread_id = event.button.name
        event.stop()
        self.dismiss(thread_id)


class ThreadMetadataView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Return"),
    ]

    def __init__(
        self,
        thread_id: str,
        thread_name: str,
        thread_description: str,
        *args,
        **kwargs,
    ):
        self.thread_id = thread_id
        self.thread_name = thread_name
        self.thread_description = thread_description
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        yield t_widgets.Label(f"Thread: {self.thread_id}")

        with t_containers.Grid():
            yield t_widgets.Label("Thread name:")
            yield t_widgets.Input(self.thread_name, id="thread-name")

        with t_containers.Grid():
            yield t_widgets.Label("Description:")
            yield t_widgets.Input(self.thread_description, id="thread-desc")

        yield t_widgets.Footer()

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        w_name = self.query_one("#thread-name")
        w_desc = self.query_one("#thread-desc")
        self.dismiss(
            {
                "name": w_name.value.strip(),
                "description": w_desc.value.strip(),
            }
        )


class Prompt(t_widgets.Markdown):
    """Markdown for the user prompt."""


class Response(t_widgets.Markdown):
    """Markdown for the reply from the LLM."""

    BORDER_TITLE = "Soliplex"


class RoomThreadWidget(t_widget.Widget):
    DEFAULT_CSS = """
    RoomThreadWidget {
        layout: horizontal;
        height: auto;
    }
    RoomThreadWidget Label {
        padding-right: 2;
    }
    """


class RoomView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("ctrl+n", "new_thread", "New thread"),
        t_binding.Binding("ctrl+t", "list_threads", "Threads"),
        t_binding.Binding("ctrl+r", "list_runs", "Runs"),
        t_binding.Binding("ctrl+z", "edit_metadata", "Metadata"),
        t_binding.Binding("escape", "app.pop_screen", "Exit room"),
    ]

    AUTO_FOCUS = "Input"
    CSS = """
    Prompt {
        background: $primary 10%;
        color: $text;
        margin: 1;        
        margin-right: 8;
        padding: 1 2 0 2;
    }

    Response {
        border: wide $success;
        background: $success 10%;   
        color: $text;             
        margin: 1;      
        margin-left: 8; 
        padding: 1 2 0 2;
    }
    """

    thread_id: str | None = t_reactive.reactive(None, bindings=True)
    thread_name: str | None = t_reactive.reactive(None, always_update=True)
    thread_description: str | None = None
    run_agent_input: agui_core.RunAgentInput | None = None
    run_count: int = 0

    def __init__(self, room_id, room_info, *args, **kwargs):
        self.room_id = room_id
        self.room_info = room_info
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        room_info = self.room_info
        yield t_widgets.Header()
        with RoomThreadWidget():
            yield t_widgets.Label(f"Room: {self.room_id}", id="room")
            yield t_widgets.Label(id="thread")

        with t_containers.VerticalScroll(id="chat-view"):
            yield t_widgets.Static(room_info["welcome_message"])
            yield t_widgets.Static("Suggestions:")

            for suggestion in room_info["suggestions"]:
                yield t_widgets.Static(f"- {suggestion}")

        yield t_widgets.Input(placeholder="How can I help you?")
        yield t_widgets.Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-view").anchor()
        self.thread_id = None

    def watch_thread_name(self, new_value: str | None):
        thread_label = self.query_one("#thread")

        if new_value is None:
            if self.thread_id is None:
                new_value = "<new thread>"
            else:
                new_value = self.thread_id

        thread_label.update(f"Thread: {new_value}")

    def action_new_thread(self) -> None:
        self.thread_id = self.run_agent_input = None
        self.thread_name = self.thread_description = None
        scroller = self.query_one("#chat-view")
        scroller.remove_children()
        scroller.mount(t_widgets.Static(self.room_info["welcome_message"]))
        scroller.mount(t_widgets.Static("Suggestions:"))

        for suggestion in self.room_info["suggestions"]:
            scroller.mount(t_widgets.Static(f"- {suggestion}"))

    @textual.work
    async def action_list_threads(self) -> None:
        room_threads_view = RoomThreadsView(self.room_id)

        found = await self.app.push_screen_wait(room_threads_view)

        if found is not None:
            self.select_thread(found)

    @textual.work
    async def action_list_runs(self) -> None:
        thread_runs_view = ThreadRunsView(self.room_id, self.thread_id)

        await self.app.push_screen_wait(thread_runs_view)

    @textual.work
    async def action_edit_metadata(self) -> None:
        thread_meta_view = ThreadMetadataView(
            self.thread_id,
            self.thread_name,
            self.thread_description,
        )

        found = await self.app.push_screen_wait(thread_meta_view)

        if found is not None:
            requests.post(
                f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}/agui/"
                f"{self.thread_id}/meta",
                json=found,
            )

            self.thread_name = found["name"]
            self.thread_description = found["description"]

    def check_action(self, action, parameters):
        if action in ("list_runs", "edit_metadata"):
            return self.thread_id is not None

        return True

    def select_thread(self, thread_id: str):
        self.thread_id = thread_id
        room_url = f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}"
        thread_url = f"{room_url}/agui/{thread_id}"

        info = requests.get(thread_url).json()
        meta = info.get("metadata")

        if meta is not None:
            self.thread_name = meta["name"]
            self.thread_description = meta.get("description")
        else:
            self.thread_name = None
            self.thread_description = None

        runs = list(info["runs"].values())
        self.run_count = len(info["runs"])

        rai = None
        scroller = self.query_one("#chat-view")
        scroller.remove_children()

        last_run = runs[-1]
        run_input = last_run["run_input"]

        if run_input is not None:
            rai = agui_core.RunAgentInput.model_validate(run_input)
            esp = agui_parser.EventStreamParser(rai)
            run_url = f"{thread_url}/{last_run['run_id']}"
            full_run_info = requests.get(run_url).json()

            for event_info in full_run_info["events"]:
                event = agui_parser.agui_event_from_json(event_info)
                esp(event)

            self.run_agent_input = esp.as_run_agent_input

            for message in esp.messages:
                if message.role == "user":
                    scroller.mount(Prompt(message.content))
                elif (
                    message.role == "assistant" and message.content is not None
                ):
                    scroller.mount(Response(message.content))

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        chat_view = self.query_one("#chat-view")
        event.input.clear()
        await chat_view.mount(Prompt(event.value))
        await chat_view.mount(response := Response())

        self.send_agui_prompt(event.value, response)

    @textual.work(thread=True)
    def send_agui_prompt(self, prompt: str, response: Response) -> None:
        """Get the AG-UI response in a thread."""
        self.run_count += 1
        response_content = ""
        room_url = f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}"
        room_agui_url_base = f"{room_url}/agui"

        if self.run_agent_input is None:
            new_thread_request_url = room_agui_url_base
            new_thread_request_json = {
                "name": f"{self.room_id}: {prompt}",
            }
            new_thread = requests.post(
                new_thread_request_url,
                json=new_thread_request_json,
            ).json()
            self.thread_id = thread_id = new_thread["thread_id"]
            (run_id,) = new_thread["runs"].keys()

            self.run_agent_input = agui_core.RunAgentInput(
                thread_id=thread_id,
                run_id=run_id,
                state={},
                messages=[
                    {"id": "user_001", "role": "user", "content": prompt}
                ],
                tools=[],
                context=[],
                forwarded_props={},
            )
        else:
            thread_id = self.run_agent_input.thread_id
            new_run_request_url = f"{room_agui_url_base}/{thread_id}"
            new_run_request_json = {}
            new_run = requests.post(
                new_run_request_url,
                json=new_run_request_json,
            ).json()
            run_id = new_run["run_id"]
            self.run_agent_input.parent_run_id = new_run["parent_run_id"]
            self.run_agent_input.run_id = run_id

            self.run_agent_input.messages.append(
                agui_core.UserMessage(
                    id=f"user_{self.run_count:03}",
                    content=prompt,
                )
            )

        event_log = []
        esp = agui_parser.EventStreamParser(
            self.run_agent_input,
            event_log=event_log,
            stripped_message_types=agui_core.ActivityMessage,
        )
        request_json = self.run_agent_input.model_dump()

        request_url = f"{room_agui_url_base}/{thread_id}/{run_id}"
        streaming_response = requests.post(
            request_url,
            json=request_json,
            stream=True,
        )

        for line in streaming_response.iter_lines():
            if line:
                decoded = line.decode("utf-8")

                if decoded.startswith("data: "):
                    decoded = decoded[len("data: ") :]

                chunk = json.loads(decoded)
                event = agui_parser.agui_event_from_json(chunk)
                esp(event)

                if chunk["type"] == "THINKING_START":
                    response_content += "\n\n** thinking **\n\n"

                elif chunk["type"] == "THINKING_TEXT_MESSAGE_CONTENT":
                    response_content += chunk["delta"]

                elif chunk["type"] == "TOOL_CALL_START":
                    response_content += (
                        f"\n\n** calling tool {chunk['toolCallName']} **"
                    )

                elif chunk["type"] == "TEXT_MESSAGE_START":
                    response_content += "\n\n** response **\n\n"

                elif chunk["type"] == "TEXT_MESSAGE_CONTENT":
                    response_content += chunk["delta"]

                elif chunk["type"] == "ACTIVITY_SNAPSHOT":
                    response_content += (
                        f"\n\n** activity **\n\n{chunk['content']}\n\n"
                    )

                elif chunk["type"] == "RUN_FINISHED":
                    response_content += "\n\n** done **"

                elif chunk["type"] == "RUN_ERROR":
                    response_content += (
                        f"\n\n** error **\n\n{chunk['message']}"
                    )

                self.app.call_from_thread(response.update, response_content)

        new_run_agent_input = esp.as_run_agent_input

        self.run_agent_input.messages[:] = new_run_agent_input.messages[:]


class SoliplexTUI(t_app.App):
    TITLE = "Soliplex TUI"

    BINDINGS = [
        t_binding.Binding("ctrl+q", "quit", "quit", id="quit"),
    ]

    def __init__(self, soliplex_url="http://localhost:8000", *args, **kw):
        self.soliplex_url = soliplex_url
        self._rooms = None

        super().__init__(*args, **kw)

    def on_mount(self) -> None:
        self.border_subtitle = self.soliplex_url

    @property
    def rooms(self) -> dict[str, dict]:
        if self._rooms is None:
            self._rooms = requests.get(
                f"{self.soliplex_url}/api/v1/rooms",
            ).json()

        return self._rooms

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label("Available rooms:")
        with t_containers.VerticalScroll(id="rooms-list"):
            for room_id, room_info in self.rooms.items():
                yield t_widgets.Button(
                    name=room_id,
                    label=f"{room_id}: {room_info['description']}",
                )
        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        room_id = event.button.name
        room_info = self.rooms[room_id]
        room_view = RoomView(room_id, room_info)
        await self.push_screen(room_view)


if __name__ == "__main__":
    app = SoliplexTUI()
    app.run()

import json

import requests
import textual
from ag_ui import core as agui_core
from textual import app as t_app
from textual import binding as t_binding
from textual import containers as t_containers
from textual import reactive as t_reactive
from textual import screen as t_screen
from textual import widgets as t_widgets

from soliplex.agui import parser as agui_parser


class RoomThreadsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding(
            "escape",
            "dismiss(None)",
            "Return to room",
        ),
    ]

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
                yield t_widgets.Button(
                    name=thread_id,
                    label=f"{thread_id}",
                )
        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        thread_id = event.button.name
        event.stop()
        self.dismiss(thread_id)


class Prompt(t_widgets.Markdown):
    """Markdown for the user prompt."""


class Response(t_widgets.Markdown):
    """Markdown for the reply from the LLM."""

    BORDER_TITLE = "Soliplex"


class RoomView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("ctrl+n", "new_thread", "New thread"),
        t_binding.Binding("ctrl+t", "list_threads", "List threads"),
        t_binding.Binding("escape", "app.pop_screen", "Return to room list"),
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

    thread_id: str | None = t_reactive.reactive(None)
    run_agent_input: agui_core.RunAgentInput | None = None
    run_count: int = 0

    def __init__(self, room_id, room_info, *args, **kwargs):
        self.room_id = room_id
        self.room_info = room_info
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        room_info = self.room_info
        yield t_widgets.Header()
        yield t_widgets.Label(id="room-thread")

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

    def watch_thread_id(self, new_value: str | None):
        room_thread = self.query_one("#room-thread")
        if new_value is None:
            room_thread.update(f"Room: {self.room_id} | Thread: <new thread>")
        else:
            room_thread.update(f"Room: {self.room_id} | Thread: {new_value}")

    def action_new_thread(self) -> None:
        self.thread_id = self.run_agent_input = None
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

    def select_thread(self, thread_id: str):
        self.thread_id = thread_id
        room_url = f"{self.app.soliplex_url}/api/v1/rooms/{self.room_id}"
        thread_url = f"{room_url}/agui/{thread_id}"

        info = requests.get(thread_url).json()

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

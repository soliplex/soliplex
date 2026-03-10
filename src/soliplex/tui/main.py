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
from soliplex.config.agui import AGUI_FEATURES_BY_NAME
from soliplex.tui import rest_api


class ListHeaderWidget(t_widget.Widget):
    DEFAULT_CSS = """
    ListHeaderWidget {
        layout: horizontal;
        height: auto;
        padding: 1;
    }
    ListHeaderWidget Label {
        padding-right: 2;
    }
    """


class LabeledInputWidget(t_widget.Widget):
    DEFAULT_CSS = """
    LabeledInputWidget {
        layout: horizontal;
        height: auto;
        padding: 1;
    }
    LabeledInputWidget Label {
        width: 20;
        text-align: right;
        padding: 1
    }
    LabeledInputWidget Input {
        width: 1fr;
        text-align: left;
    }
    """


class LoginDialog(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
    ]

    def __init__(
        self,
        oidc_provider: dict,
        *args,
        **kwargs,
    ):
        self._oidc_provider = oidc_provider
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        yield t_widgets.Label(f"Login: {self._oidc_provider['title']}")

        with LabeledInputWidget():
            yield t_widgets.Label("Username:")
            yield t_widgets.Input("", id="username")

        with LabeledInputWidget():
            yield t_widgets.Label("Password:")
            yield t_widgets.Input("", id="password", password=True)

        yield t_widgets.Footer()

    @property
    def oidc_provider_token_data(self):
        oidc_provider = self._oidc_provider
        result = {
            "client_id": oidc_provider["client_id"],
            "grant_type": "password",
        }
        client_secret = oidc_provider.get("client_secret")

        if client_secret is not None:
            result["client_secret"] = client_secret

        return result

    @property
    def oidc_provider_token_url(self):
        base = self._oidc_provider["server_url"]
        return f"{base}/protocol/openid-connect/token"

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""

        w_username = self.query_one("#username")
        username = w_username.value.strip()

        w_password = self.query_one("#password")
        password = w_password.value.strip()

        payload = {
            "username": username,
            "password": password,
        }

        self.dismiss(payload)


class OIDCProviderSelectView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
    ]

    def __init__(
        self,
        oidc_providers: list[dict],
        *args,
        **kwargs,
    ):
        self.oidc_providers = oidc_providers
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        with ListHeaderWidget():
            yield t_widgets.Label("Select OIDC Provider:")

        with t_containers.VerticalScroll(id="provider-list"):
            for provider_id, provider_info in self.oidc_providers.items():
                yield t_widgets.Button(
                    name=provider_id,
                    label=f"{provider_id}:\n{provider_info['title']}",
                    variant="primary",
                )

        yield t_widgets.Footer()

    @textual.work
    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        provider_id = event.button.name
        provider_info = self.oidc_providers[provider_id]
        login_dialog = LoginDialog(provider_info)
        payload = await self.app.push_screen_wait(login_dialog)

        if payload:
            token_url = login_dialog.oidc_provider_token_url
            token_request = login_dialog.oidc_provider_token_data | payload
            response = requests.post(token_url, data=token_request)
            response.raise_for_status()
            token_data = response.json()
            self.dismiss((token_url, token_data))
        else:
            self.dismiss(None)


class EditRunMetadataDialog(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
    ]

    def __init__(self, run_id: str, label_text: str, *args, **kwargs):
        self.run_id = run_id
        self.label_text = label_text
        super().__init__()

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        yield t_widgets.Label(f"Run UUID: {self.run_id}")

        with LabeledInputWidget():
            yield t_widgets.Label("Label")
            yield t_widgets.Input(self.label_text)

        yield t_widgets.Footer()

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        payload = {}
        label = event.value.strip()

        if label:
            payload["label"] = label

        self.dismiss(payload)


class EditThreadMetadataDialog(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
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

        yield t_widgets.Label(f"Thread UUID: {self.thread_id}")

        with LabeledInputWidget():
            yield t_widgets.Label("Thread name:")
            yield t_widgets.Input(self.thread_name, id="thread-name")

        with LabeledInputWidget():
            yield t_widgets.Label("Description:")
            yield t_widgets.Input(self.thread_description, id="thread-desc")

        yield t_widgets.Footer()

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        payload = {}

        w_name = self.query_one("#thread-name")
        name = w_name.value.strip()

        w_desc = self.query_one("#thread-desc")
        desc = w_desc.value.strip()

        if name:
            payload["name"] = name

            if desc:
                payload["description"] = desc

        self.dismiss(payload)


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


class StateViewModal(t_screen.ModalScreen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Close"),
    ]
    DEFAULT_CSS = """
    StateViewModal {
        align: center middle;
    }
    StateViewModal > Container {
        width: 80%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    StateViewModal > Container > Label {
        text-style: bold;
        margin-bottom: 1;
    }
    StateViewModal > Container > VerticalScroll {
        height: 1fr;
    }
    """

    def __init__(self, state: dict, *args, **kwargs):
        self.state = state
        super().__init__(*args, **kwargs)

    def compose(self) -> t_app.ComposeResult:
        from rich import syntax as rich_syntax

        with t_containers.Container():
            yield t_widgets.Label("AG-UI State")
            with t_containers.VerticalScroll():
                state_json = json.dumps(self.state, indent=2)
                syntax = rich_syntax.Syntax(
                    state_json,
                    "json",
                    line_numbers=True,
                )
                yield t_widgets.Static(syntax)


class RunView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
        t_binding.Binding("ctrl+z", "edit_metadata", "Metadata"),
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
    def rest_api(self) -> rest_api.TUI_REST_API:
        return self.app.rest_api

    @property
    def run_info(self) -> dict[str, dict]:
        if self._run_info is None:
            self._run_info = self.rest_api.get_run(
                self.room_id,
                self.thread_id,
                self.run_id,
            )

        return self._run_info

    @property
    def run_events(self) -> list[dict]:
        return self.run_info.get("events", [])

    @property
    def run_messages(self) -> list[dict]:
        run_input = self.run_info.get("run_input") or {}
        return run_input.get("messages", [])

    @property
    def run_meta(self) -> dict[str, str]:
        return self.run_info.get("metadata", {})

    @property
    def run_usage(self) -> dict[str, int]:
        return self.run_info.get("usage", {})

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
    async def action_edit_metadata(self) -> None:
        ermd = EditRunMetadataDialog(self.run_id, self.label_text)
        payload = await self.app.push_screen_wait(ermd)

        if payload is not None:
            self.rest_api.post_run_metadata(
                self.room_id,
                self.thread_id,
                self.run_id,
                payload,
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
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
    ]
    DEFAULT_CSS = """
    .run-label {
        padding: 1;
    }
    """

    def __init__(self, room_id, thread_id, thread_name, *args, **kwargs):
        self.room_id = room_id
        self.thread_id = thread_id
        self.thread_name = thread_name
        self._runs = None
        super().__init__()

    @property
    def rest_api(self) -> rest_api.TUI_REST_API:
        return self.app.rest_api

    @property
    def runs(self) -> dict[str, dict]:
        if self._runs is None:
            info = self.rest_api.get_thread(
                self.room_id,
                self.thread_id,
            )
            self._runs = info["runs"]

        return self._runs

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        with ListHeaderWidget():
            yield t_widgets.Label(
                f"Runs in thread: {self.thread_name or self.thread_id}",
            )

        with t_containers.VerticalScroll(id="runs-list"):
            for run_id, run_info in self.runs.items():
                meta = run_info["metadata"]

                if meta is not None:
                    button_label = f"{meta['label']}:\n{run_id}"
                else:
                    button_label = run_id

                with RunButtonWidget():
                    yield t_widgets.Button(
                        name=run_id,
                        label=button_label,
                        variant="primary",
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
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
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
    def rest_api(self) -> rest_api.TUI_REST_API:
        return self.app.rest_api

    @property
    def threads(self) -> dict[str, dict]:
        if self._threads is None:
            info = self.rest_api.get_room_threads(self.room_id)
            self._threads = info["threads"]
            self._threads_by_id = {
                thread_info["thread_id"]: thread_info
                for thread_info in self._threads
            }

        return self._threads

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        threads = self.threads

        with ListHeaderWidget():
            if threads:
                yield t_widgets.Label(f"Threads in room: {self.room_id}")
            else:
                yield t_widgets.Label(f"No threads in room: {self.room_id}")

        with t_containers.VerticalScroll(id="threads-list"):
            for thread_info in self.threads:
                thread_id = thread_info["thread_id"]
                meta = thread_info.get("metadata")

                if meta is not None:
                    button_label = f"{meta['name']}:\n{thread_id}"
                else:
                    button_label = thread_id

                with ThreadButtonWidget():
                    yield t_widgets.Button(
                        name=thread_id,
                        label=button_label,
                        variant="primary",
                    )

        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        thread_id = event.button.name
        event.stop()
        self.dismiss(thread_id)


class MCPTokenView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "dismiss(None)", "Exit"),
    ]
    DEFAULT_CSS = """
    MCPTokenView Static {
        padding: 1;
        text-wrap: wrap;
    }
    """

    def __init__(self, room_id, *args, **kwargs):
        self.room_id = room_id
        super().__init__()

    @property
    def rest_api(self) -> rest_api.TUI_REST_API:
        return self.app.rest_api

    @property
    def mcp_token(self) -> str:
        response = self.rest_api.get_room_mcp_token(self.room_id)
        return response["mcp_token"]

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label(f"Room MCP token: {self.room_id}")
        yield t_widgets.Static(
            "Copy this string for use in your MCP browser:",
        )
        yield t_widgets.Static(self.mcp_token)
        yield t_widgets.Footer()


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
        t_binding.Binding("ctrl+s", "view_state", "State"),
        t_binding.Binding("ctrl+z", "edit_metadata", "Metadata"),
        t_binding.Binding("ctrl+p", "mcp_token", "MCP Token"),
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
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

    @property
    def rest_api(self) -> rest_api.TUI_REST_API:
        return self.app.rest_api

    @property
    def verbose(self) -> bool:
        return self.app.verbose

    def _build_initial_state(self) -> dict:
        """Build initial AG-UI state based on room features."""
        state = {}
        feature_names = self.room_info.get("agui_feature_names", [])
        for feature_name in feature_names:
            feature = AGUI_FEATURES_BY_NAME.get(feature_name)
            if feature is not None:
                state[feature_name] = feature.model_klass().model_dump(
                    mode="json"
                )
        return state

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
        thread_runs_view = ThreadRunsView(
            self.room_id,
            self.thread_id,
            self.thread_name,
        )

        await self.app.push_screen_wait(thread_runs_view)

    @textual.work
    async def action_view_state(self) -> None:
        state = {}
        if self.run_agent_input is not None:
            state = self.run_agent_input.state
        await self.app.push_screen_wait(StateViewModal(state))

    @textual.work
    async def action_edit_metadata(self) -> None:
        thread_meta_view = EditThreadMetadataDialog(
            self.thread_id,
            self.thread_name,
            self.thread_description,
        )

        payload = await self.app.push_screen_wait(thread_meta_view)

        if payload is not None:
            self.rest_api.post_thread_metadata(
                self.room_id,
                self.thread_id,
                payload,
            )

            self.thread_name = payload.get("name")
            self.thread_description = payload.get("description")

    @textual.work
    async def action_mcp_token(self) -> None:
        mcp_token_view = MCPTokenView(
            self.room_id,
        )

        await self.app.push_screen_wait(mcp_token_view)

    def check_action(self, action, parameters):
        if action in ("list_runs", "edit_metadata", "new_thread"):
            return self.thread_id is not None

        return True

    def select_thread(self, thread_id: str):
        self.thread_id = thread_id
        info = self.rest_api.get_thread(self.room_id, thread_id)
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
            full_run_info = self.rest_api.get_run(
                self.room_id,
                thread_id,
                last_run["run_id"],
            )

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

        if self.run_agent_input is None:
            request = {
                "name": f"{self.room_id}: {prompt}",
            }
            new_thread = self.rest_api.post_new_thread(self.room_id, request)

            self.thread_id = thread_id = new_thread["thread_id"]
            self.thread_name = None
            (run_id,) = new_thread["runs"].keys()

            self.run_agent_input = agui_core.RunAgentInput(
                thread_id=thread_id,
                run_id=run_id,
                state=self._build_initial_state(),
                messages=[
                    {"id": "user_001", "role": "user", "content": prompt}
                ],
                tools=[],
                context=[],
                forwarded_props={},
            )
        else:
            thread_id = self.run_agent_input.thread_id
            new_run = self.rest_api.post_new_run(
                self.room_id,
                thread_id,
                request={},
            )
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
        )

        streaming_response = self.rest_api.post_start_run(
            self.room_id,
            thread_id,
            run_id,
            self.run_agent_input,
        )

        for line in streaming_response.iter_lines():
            if line:
                decoded = line.decode("utf-8")

                if decoded.startswith(":"):  # comment, i.e., keepalive
                    continue

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

                elif chunk["type"] == "STATE_SNAPSHOT" and self.verbose:
                    response_content += (
                        f"\n\n** state snapshot **\n\n{chunk['snapshot']}\n\n"
                    )

                elif chunk["type"] == "STATE_DELTA" and self.verbose:
                    response_content += (
                        f"\n\n** state delta **\n\n{chunk['delta']}\n\n"
                    )

                elif chunk["type"] == "ACTIVITY_SNAPSHOT" and self.verbose:
                    response_content += (
                        f"\n\n** activity snapshot "
                        f"**\n\n{chunk['content']}\n\n"
                    )

                elif chunk["type"] == "ACTIVITY_DELTA" and self.verbose:
                    response_content += (
                        f"\n\n** activity delta**\n\n{chunk['patch']}\n\n"
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
        self.run_agent_input.state = new_run_agent_input.state


class RoomListView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
    ]

    def __init__(self, *args, **kw):
        self._rooms = None

        super().__init__(*args, **kw)

    @property
    def rooms(self) -> dict[str, dict]:
        attempts = 0
        while self._rooms is None and attempts < 3:
            self._rooms = self.app.rest_api.get_rooms()

        return self._rooms

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()

        with ListHeaderWidget():
            yield t_widgets.Label("Available rooms:")

        with t_containers.VerticalScroll(id="rooms-list"):
            for room_id, room_info in self.rooms.items():
                yield t_widgets.Button(
                    name=room_id,
                    label=f"{room_id}:\n{room_info['description']}",
                    variant="primary",
                )
        yield t_widgets.Footer()

    async def on_button_pressed(
        self,
        event: t_widgets.Button.Pressed,
    ) -> None:
        room_id = event.button.name
        room_info = self.rooms[room_id]
        room_view = RoomView(room_id, room_info)
        await self.app.push_screen(room_view)


class RoomConfigsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
    ]

    def __init__(self, room_configs, *args, **kw):
        self._room_configs = room_configs

        super().__init__(*args, **kw)

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label("Room Configurations")
        tree = t_widgets.Tree(label="Root")
        tree.add_json(self._room_configs)
        tree.root.expand()
        yield tree
        yield t_widgets.Footer()


class InstalledVersionsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
    ]

    def __init__(self, installed_versions, *args, **kw):
        self._installed_versions = installed_versions

        super().__init__(*args, **kw)

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label("Installed Versions")
        tree = t_widgets.Tree(label="Root")
        tree.add_json(self._installed_versions)
        tree.root.expand()
        yield tree
        yield t_widgets.Footer()


class ProviderModelsView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
    ]

    def __init__(self, provider_models, *args, **kw):
        self._provider_models = provider_models

        super().__init__(*args, **kw)

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label("Provider Models")
        tree = t_widgets.Tree(label="Root")
        tree.add_json(self._provider_models)
        tree.root.expand()
        yield tree
        yield t_widgets.Footer()


class InstallationConfigView(t_screen.Screen):
    BINDINGS = [
        t_binding.Binding("ctrl+r", "room_configs", "Rooms"),
        t_binding.Binding("ctrl+v", "installed_versions", "Versions"),
        t_binding.Binding("ctrl+d", "provider_models", "Providers"),
        t_binding.Binding("escape", "app.pop_screen", "Exit"),
    ]

    def __init__(self, installation_config, *args, **kw):
        self._installation_config = installation_config

        super().__init__(*args, **kw)

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        yield t_widgets.Label("Installation Configuration")
        tree = t_widgets.Tree(label="Root")
        tree.add_json(self._installation_config)
        tree.root.expand()
        yield tree
        yield t_widgets.Footer()

    @textual.work
    async def action_room_configs(self) -> None:
        room_configs = self.app.rest_api.get_rooms()

        rc_view = RoomConfigsView(room_configs)
        await self.app.push_screen_wait(rc_view)

    @textual.work
    async def action_installed_versions(self) -> None:
        installed_versions = self.app.rest_api.get_installed_versions()

        iv_view = InstalledVersionsView(installed_versions)
        await self.app.push_screen_wait(iv_view)

    @textual.work
    async def action_provider_models(self) -> None:
        provider_models = self.app.rest_api.get_provider_models()

        iv_view = ProviderModelsView(provider_models)
        await self.app.push_screen_wait(iv_view)


class SoliplexTUI(t_app.App):
    TITLE = "Soliplex TUI"

    BINDINGS = [
        t_binding.Binding("ctrl+n", "installation_config", "Installation"),
        t_binding.Binding("ctrl+q", "quit", "quit", id="quit"),
    ]
    COMMAND_PALETTE_BINDING = "ctrl+backslash"
    DEFAULT_CSS = """
    VerticalScroll {
        width: 100%;
    }
    VerticalScroll Button {
        width: 100%;
    }
    """

    def __init__(
        self,
        soliplex_url: str = "http://localhost:8000",
        verbose: bool = False,
        *args,
        **kw,
    ):
        self.soliplex_url = soliplex_url
        self.verbose = verbose
        self.rest_api = rest_api.TUI_REST_API(soliplex_url)
        self._oidc_providers = None

        super().__init__(*args, **kw)

    @textual.work
    async def on_mount(self) -> None:
        self.border_subtitle = self.soliplex_url
        self._oidc_providers = self.rest_api.get_oidc_providers()

        if self._oidc_providers:
            oidcps_view = OIDCProviderSelectView(self._oidc_providers)
            oidc_response = await self.push_screen_wait(oidcps_view)

            if oidc_response is None:
                self.exit("Authentication failed", 1)

            token_url, token_data = oidc_response
            self.rest_api.oidc_token_url = token_url
            self.rest_api.oidc_token_data = token_data

        rl_view = RoomListView()
        await self.push_screen_wait(rl_view)

    @textual.work
    async def action_installation_config(self) -> None:
        config = self.rest_api.get_installation()

        ic_view = InstallationConfigView(config)
        await self.push_screen_wait(ic_view)


app = SoliplexTUI()

if __name__ == "__main__":
    status = app.run()
    if status is not None:
        print(status)

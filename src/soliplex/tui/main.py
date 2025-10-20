import json

import requests
import textual
from textual import app as t_app
from textual import binding as t_binding
from textual import containers as t_containers
from textual import screen as t_screen
from textual import widgets as t_widgets


class Prompt(t_widgets.Markdown):
    """Markdown for the user prompt."""


class Response(t_widgets.Markdown):
    """Markdown for the reply from the LLM."""

    BORDER_TITLE = "Soliplex"


class SoliplexTUI(t_app.App):
    TITLE = "soliplex-tui"
    SUB_TITLE = "the Soliplex TUI client."

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

    BINDINGS = [
        t_binding.Binding("ctrl+q", "quit", "quit", id="quit"),
    ]

    def __init__(self, soliplex_url, room_id, *args, **kwargs):
        self.soliplex_url = soliplex_url
        self.room_id = room_id
        self.convo_uuid = None
        super().__init__(*args, **kwargs)

    def compose(self) -> t_app.ComposeResult:
        yield t_widgets.Header()
        with t_containers.VerticalScroll(id="chat-view"):
            yield Response(f"Room: {self.room_id}")
        yield t_widgets.Input(placeholder="How can I help you?")
        yield t_widgets.Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-view").anchor()

    @textual.on(t_widgets.Input.Submitted)
    async def on_input(self, event: t_widgets.Input.Submitted) -> None:
        """When the user hits return."""
        chat_view = self.query_one("#chat-view")
        event.input.clear()
        await chat_view.mount(Prompt(event.value))
        await chat_view.mount(response := Response())
        self.send_prompt(event.value, response)

    @textual.work(thread=True)
    def send_prompt(self, prompt: str, response: Response) -> None:
        """Get the response in a thread."""
        response_content = ""
        request_json = {
            "text": prompt,
        }
        if self.convo_uuid is None:
            request_url = (
                f"{self.soliplex_url}/api/v1/convos/new/{self.room_id}"
            )
            convo_response = requests.post(request_url, json=request_json)
            convo = convo_response.json()
            self.convo_uuid = convo["convo_uuid"]
            response_content = convo["message_history"][-1]["text"]
            self.call_from_thread(response.update, response_content)
        else:
            request_url = (
                f"{self.soliplex_url}/api/v1/convos/{self.convo_uuid}"
            )
            streaming_response = requests.post(
                request_url, json=request_json, stream=True,
            )
            for line in streaming_response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    chunk = json.loads(decoded)
                    # Soliplex streams the whole thing
                    #response_content += chunk["content"]
                    self.call_from_thread(response.update, chunk["content"])

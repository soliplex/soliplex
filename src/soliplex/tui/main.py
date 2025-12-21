#
#   Note: debugging output emitted below via 'print' / 'pprint' will only
#         be visible in another terminal running 'textual console'.
#
#         Recommended command line for the TUI:
#         $ textual run --dev soliplex.tui.cli:the_cli \
#             -- --use-aguie -r <room_id>
#
#         Recommended command line for the console:
#         $ textual console -x SYSTEM -x EVENT -x DEBUG
#
import json
import pprint

import requests
import textual
from ag_ui import core as agui_core
from textual import app as t_app
from textual import binding as t_binding
from textual import containers as t_containers
from textual import widgets as t_widgets

from soliplex.agui import parser as agui_parser


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
        self.run_agent_input = None
        self.run_count = 0
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

        self.send_agui_prompt(event.value, response)

    @textual.work(thread=True)
    def send_agui_prompt(self, prompt: str, response: Response) -> None:
        """Get the AG-UI response in a thread."""
        self.run_count += 1
        response_content = ""
        room_agui_url_base = (
            f"{self.soliplex_url}/api/v1/rooms/{self.room_id}/agui"
        )

        if self.run_agent_input is None:
            print("X" * 50)
            print("New thread")
            print("X" * 50)

            new_thread_request_url = room_agui_url_base
            new_thread_request_json = {
                "name": f"{self.room_id}: {prompt}",
            }
            new_thread = requests.post(
                new_thread_request_url,
                json=new_thread_request_json,
            ).json()
            thread_id = new_thread["thread_id"]
            (run_id,) = new_thread["runs"].keys()
            print(f"New thread ID: {thread_id}")
            print(f"New run ID: {thread_id}")

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
            print("X" * 50)
            print(f"Existing thread: {thread_id}")
            print("X" * 50)
            new_run_request_url = f"{room_agui_url_base}/{thread_id}"
            new_run_request_json = {}
            new_run = requests.post(
                new_run_request_url,
                json=new_run_request_json,
            ).json()
            run_id = new_run["run_id"]
            print(f"New run ID: {run_id}")
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
            # Working around Pydantic-AI issue:
            # https://github.com/pydantic/pydantic-ai/issues/3802
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

                self.call_from_thread(response.update, response_content)

        new_run_agent_input = esp.as_run_agent_input

        self.run_agent_input = new_run_agent_input

        print(f"Streamed {len(event_log)} events:")
        for event in event_log:
            pprint.pprint(event.model_dump())

        print(f"Retained {len(new_run_agent_input.messages)} messages")
        for message in new_run_agent_input.messages:
            pprint.pprint(message.model_dump())

import dataclasses

import requests
from ag_ui import core as agui_core

from soliplex import models


@dataclasses.dataclass
class TUI_REST_API:
    soliplex_url: str

    @property
    def api_base(self):
        return f"{self.soliplex_url}/api"

    @property
    def api_v1_base(self):
        return f"{self.api_base}/v1"

    def room_agui_base(self, room_id: str) -> str:
        return f"{self.api_v1_base}/rooms/{room_id}/agui"

    def thread_url(self, room_id: str, thread_id: str) -> str:
        return f"{self.room_agui_base(room_id)}/{thread_id}"

    def run_url(self, room_id: str, thread_id: str, run_id: str) -> str:
        return f"{self.thread_url(room_id, thread_id)}/{run_id}"

    def get_rooms(self):
        return requests.get(f"{self.api_v1_base}/rooms").json()

    def get_room_threads(self, room_id: str):
        return requests.get(self.room_agui_base(room_id)).json()

    def get_thread(self, room_id: str, thread_id: str) -> models.AGUI_Thread:
        return requests.get(self.thread_url(room_id, thread_id)).json()

    def post_new_thread(
        self,
        room_id,
        request: models.AGUI_NewThreadRequest | dict,
    ):
        new_thread_request_url = self.room_agui_base(room_id)

        if isinstance(request, models.AGUI_NewThreadRequest):
            request = request.model_dump()

        return requests.post(new_thread_request_url, json=request).json()

    def post_thread_metadata(
        self,
        room_id: str,
        thread_id: str,
        meta: models.AGUI_ThreadMetadata | dict,
    ) -> None:
        meta_url = f"{self.thread_url(room_id, thread_id)}/meta"

        if isinstance(meta, models.AGUI_ThreadMetadata):
            meta = meta.model_dump()

        requests.post(meta_url, json=meta)

    def post_new_run(
        self,
        room_id: str,
        thread_id: str,
        request: models.AGUI_NewRunRequest | dict,
    ):
        new_run_request_url = self.thread_url(room_id, thread_id)

        if isinstance(request, models.AGUI_NewRunRequest):
            request = request.model_dump()

        return requests.post(new_run_request_url, json=request).json()

    def get_run(
        self,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> models.AGUI_Run:
        return requests.get(self.run_url(room_id, thread_id, run_id)).json()

    def post_start_run(
        self,
        room_id: str,
        thread_id: str,
        run_id: str,
        run_agent_input: agui_core.RunAgentInput | dict,
    ) -> requests.Response:
        run_url = self.run_url(room_id, thread_id, run_id)

        if isinstance(run_agent_input, agui_core.RunAgentInput):
            run_agent_input = run_agent_input.model_dump()

        return requests.post(run_url, json=run_agent_input, stream=True)

    def post_run_metadata(
        self,
        room_id: str,
        thread_id: str,
        run_id: str,
        meta: models.AGUI_RunMetadata | dict,
    ) -> None:
        meta_url = f"{self.run_url(room_id, thread_id, run_id)}/meta"

        if isinstance(meta, models.AGUI_RunMetadata):
            meta = meta.model_dump()

        requests.post(meta_url, json=meta)

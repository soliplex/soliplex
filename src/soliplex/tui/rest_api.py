import dataclasses

import requests
from ag_ui import core as agui_core

from soliplex import models


@dataclasses.dataclass
class TUI_REST_API:
    soliplex_url: str
    oidc_token_url: str = None
    oidc_token_data: dict[str, str] = None

    @property
    def api_base(self):
        return f"{self.soliplex_url}/api"

    @property
    def auth_url_base(self) -> str:
        return f"{self.api_base}/auth"

    def get_oidc_providers(self):
        oidc_providers_url = f"{self.api_base}/login"
        response = requests.get(oidc_providers_url)
        response.raise_for_status()

        return response.json()

    def auth_url(self, system: str) -> str:
        return f"{self.api_base}/auth"

    @property
    def api_v1_base(self):
        return f"{self.api_base}/v1"

    @property
    def api_v1_headers(self) -> dict[str, str]:
        token_data = self.oidc_token_data

        if token_data is not None:
            access_token = token_data["access_token"]
            return {"Authorization": f"Bearer {access_token}"}
        else:
            return {}

    def get_installation(self):
        response = requests.get(
            f"{self.api_v1_base}/installation",
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def get_rooms(self):
        response = requests.get(
            f"{self.api_v1_base}/rooms",
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def room_agui_base(self, room_id: str) -> str:
        return f"{self.api_v1_base}/rooms/{room_id}/agui"

    def thread_url(self, room_id: str, thread_id: str) -> str:
        return f"{self.room_agui_base(room_id)}/{thread_id}"

    def run_url(self, room_id: str, thread_id: str, run_id: str) -> str:
        return f"{self.thread_url(room_id, thread_id)}/{run_id}"

    def get_room_threads(self, room_id: str):
        response = requests.get(
            self.room_agui_base(room_id),
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def get_thread(self, room_id: str, thread_id: str) -> models.AGUI_Thread:
        response = requests.get(
            self.thread_url(room_id, thread_id),
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def post_new_thread(
        self,
        room_id,
        request: models.AGUI_NewThreadRequest | dict,
    ):
        new_thread_request_url = self.room_agui_base(room_id)

        if isinstance(request, models.AGUI_NewThreadRequest):
            request = request.model_dump()

        response = requests.post(
            new_thread_request_url,
            json=request,
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def post_thread_metadata(
        self,
        room_id: str,
        thread_id: str,
        meta: models.AGUI_ThreadMetadata | dict,
    ) -> None:
        meta_url = f"{self.thread_url(room_id, thread_id)}/meta"

        if isinstance(meta, models.AGUI_ThreadMetadata):
            meta = meta.model_dump()

        response = requests.post(
            meta_url,
            json=meta,
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

    def post_new_run(
        self,
        room_id: str,
        thread_id: str,
        request: models.AGUI_NewRunRequest | dict,
    ):
        new_run_request_url = self.thread_url(room_id, thread_id)

        if isinstance(request, models.AGUI_NewRunRequest):
            request = request.model_dump()

        response = requests.post(
            new_run_request_url,
            json=request,
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

    def get_run(
        self,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> models.AGUI_Run:
        response = requests.get(
            self.run_url(room_id, thread_id, run_id),
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

        return response.json()

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

        response = requests.post(
            run_url,
            json=run_agent_input,
            headers=self.api_v1_headers,
            stream=True,
        )
        response.raise_for_status()

        return response

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

        response = requests.post(
            meta_url,
            json=meta,
            headers=self.api_v1_headers,
        )
        response.raise_for_status()

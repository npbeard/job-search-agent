from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LinkedInOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


class LinkedInOfficialProvider:
    """
    Placeholder for approved LinkedIn OAuth-backed integrations.

    This project intentionally keeps the official provider narrow because
    LinkedIn's open access does not generally include broad people search
    or arbitrary profile discovery.
    """

    auth_base_url = "https://www.linkedin.com/oauth/v2/authorization"
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    def __init__(self, config: LinkedInOAuthConfig) -> None:
        self.config = config

    def build_authorization_url(self, state: str, scopes: list[str]) -> str:
        scope_param = "%20".join(scopes)
        return (
            f"{self.auth_base_url}?response_type=code&client_id={self.config.client_id}"
            f"&redirect_uri={self.config.redirect_uri}&state={state}&scope={scope_param}"
        )


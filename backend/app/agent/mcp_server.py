import os

from mcp.server.fastmcp import FastMCP

from app.agent.client import NetwiseApiClient


def build_server(client: NetwiseApiClient) -> FastMCP:
    server = FastMCP(
        "Netwise",
        instructions=(
            "Read household financial data and run deterministic scenario comparisons. "
            "Treat all returned data as sensitive. These tools do not modify Netwise."
        ),
    )

    @server.tool()
    def get_financial_summary() -> dict:
        """Get current assets, liabilities, and net worth for the token-bound household."""
        return client.get_financial_summary()

    @server.tool()
    def list_accounts() -> list[dict]:
        """List financial accounts and their planning metadata."""
        return client.list_accounts()

    @server.tool()
    def list_recent_balances(limit: int = 20) -> list[dict]:
        """List recent account balance snapshots, newest first. Limit must be 1 to 100."""
        return client.list_recent_balances(limit)

    @server.tool()
    def get_net_worth_history() -> dict:
        """Get the household's historical net-worth series."""
        return client.get_net_worth_history()

    @server.tool()
    def list_projection_scenarios() -> list[dict]:
        """List available deterministic projection scenarios and their IDs."""
        return client.list_projection_scenarios()

    @server.tool()
    def compare_projection_scenarios(
        scenario_ids: list[str],
        start_year: int,
        end_year: int,
    ) -> dict:
        """Compare two to four scenario IDs over an inclusive annual year range."""
        return client.compare_projection_scenarios(scenario_ids, start_year, end_year)

    return server


def client_from_environment() -> NetwiseApiClient:
    token = os.environ.get("NETWISE_API_TOKEN", "")
    base_url = os.environ.get("NETWISE_API_URL", "http://127.0.0.1:8001")
    timeout_value = os.environ.get("NETWISE_API_TIMEOUT_SECONDS", "30")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise RuntimeError("NETWISE_API_TIMEOUT_SECONDS must be a number") from exc
    if timeout_seconds <= 0:
        raise RuntimeError("NETWISE_API_TIMEOUT_SECONDS must be positive")
    try:
        return NetwiseApiClient(base_url, token, timeout_seconds=timeout_seconds)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


def main() -> None:
    client = client_from_environment()
    try:
        build_server(client).run(transport="stdio")
    finally:
        client.close()


if __name__ == "__main__":
    main()

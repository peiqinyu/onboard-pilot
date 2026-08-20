# Parent Class
class BaseConnector:
    def __init__(self, name):
        self.name = name

    def search_k_content(self, query: str, top_k: int = 3) -> str:
        return f"search top {top_k} result in {self.name} for query {query}"

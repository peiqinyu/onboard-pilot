import requests

from backend.src.memory.base_connector import BaseConnector
from typing import Dict, Any
from backend.src.memory.logger_utils import logger
from backend.src.memory.utils import my_properties
from semantic_kernel.functions import kernel_function
from typing import Annotated

"""
Connector for Linear App
"""


class LinearConnector(BaseConnector):
    def __init__(self):
        self.name = "LinearConnector"
        self.headers = {}
        self.url = ""
        # Set your API key securely
        api_key = my_properties.linear_api_key
        self.url = "https://api.linear.app/graphql"

        self.headers = {
            "Authorization": f"{api_key}",
            "Content-Type": "application/json",
        }

    def search_title(self, key_word: str):
        query = """
        query SearchIssues($term: String!, $first: Int, $includeComments: Boolean) {
          searchIssues(term: $term, first: $first, includeComments: $includeComments) {
            nodes {
              id
              identifier
              title
              url
              state {
                name
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

        variables = {
            "term": key_word,
            "first": 10,
            "includeComments": True,
        }

        response = requests.post(
            self.url,
            json={"query": query, "variables": variables},
            headers=self.headers
        )

        if response.status_code == 200:
            data = response.json()
            logger.info("Success:", data)
            return data
        else:
            logger.info(f"Failed with status code {response.status_code}: {response.text}")
            return None

    def _post(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            self.url,
            json={"query": query, "variables": variables},
            headers=self.headers,
            timeout=30,
        )

        # show actual GraphQL error body before raising
        if response.status_code != 200:
            logger.error("HTTP error:", response.status_code)
            logger.error(response.text)
            response.raise_for_status()

        data = response.json()
        if "errors" in data:
            raise Exception(f"Linear API error: {data['errors']}")
        return data["data"]

    # @kernel_function(
    #     name="search_linear_content",
    #     description="""Search and return the related issues in Linear for a given sentence."""
    # )
    def search_linear_content(self, keyword: Annotated[str, "filtered sentence, e.g. testing process looks like"],
                              first: Annotated[int, "The first k related content to return"])\
            -> Dict[str, Any]:
        # logger.debug(f"Searching in Linear for: '{keyword}'")
        logger.info(f"Searching in Linear")
        query = """
        query SearchIssues($term: String!, $first: Int!, $includeComments: Boolean) {
          searchIssues(term: $term, first: $first, includeComments: $includeComments) {
            nodes {
              id
              identifier
              title
              description
              url
              state {
                name
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

        variables = {
            "term": keyword,
            "first": first,
            "includeComments": True,
        }

        data = self._post(query, variables)

        """return format: [
        {
        "identifier": "PAI-xxx",
        "title": "xxx",
        "description": "xxx",
        "state" : {"name": "Backlog/", ...}
        "url": "https://linear.app/xxx", ...
        }, {...}, ...
        ]"""
        response = data["searchIssues"]["nodes"]
        format_response = []
        for issue in response:
            ele = {
                "source": issue['url'],
                "description": issue.get('description'),
                "title": issue['title']
            }
            format_response.append(ele)
        return format_response

    @kernel_function(
        name="search_k_content",
        description="Search and return the related issues in Linear for a given sentence."
    )
    def search_k_content(self, query: str, top_k: int = 5) -> str:
        return str(self.search_linear_content(query, top_k))


if __name__ == "__main__":
    connector = LinearConnector()
    # connector.search_content("test")
    results = connector.search_k_content("test")

    logger.debug(results)

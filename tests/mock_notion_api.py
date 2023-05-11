import uuid
from collections import Counter
from typing import Dict, Union

import httpx
import notion_client


def title(text: str) -> Dict:
    return {
        "id": "title",
        "type": "title",
        "title": [
            {
                "type": "text",
                "text": {
                    "content": text,
                    "link": "None",
                },
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "plain_text": text,
                "href": "None",
            }
        ],
    }


def number(x: Union[int, float]) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "number",
        "number": x,
    }


class FakeResponse:
    def __init__(self):
        self.query = {
            "object": "list",
            "results": [],
            "next_cursor": "None",
            "has_more": False,
            "type": "page",
            "page": {},
        }

    def add_element(self, **kwargs):
        self.query["results"].append(
            {
                "object": "page",
                "id": str(uuid.uuid4()),
                "created_time": "2023-05-07T14:02:00.000Z",
                "last_edited_time": "2023-05-07T14:08:00.000Z",
                "created_by": {"object": "user", "id": "9459043c-9999-4359-a430-c86902777967"},
                "last_edited_by": {"object": "user", "id": "9459043c-9999-4359-a430-c86902777967"},
                "cover": "None",
                "icon": "None",
                "parent": {"type": "database_id", "database_id": "f8af44d1-9999-4280-8b9c-6a55765fb1a1"},
                "archived": False,
                "properties": kwargs,
            }
        )

    def get(self):
        return self.query


# Global call counter, to know how many time each table is called through the Mock Notion API
N_CALLS = Counter()


class MockDBQuery:
    def query(self, database_id: str, **kwargs):  # noqa: C901
        N_CALLS[database_id] += 1
        if database_id == "table_with_basic_data":
            response = FakeResponse()
            response.add_element(my_title=title("Element 1"), price=number(56))
            response.add_element(my_title=title("Element 2"), price=number(98))
            return response.get()
        elif database_id == "table_api_error":
            raise notion_client.APIResponseError(httpx.Response(401), "", "")
        elif database_id == "table_filter_call_no_data":
            if "filter" not in kwargs:
                # First call
                return self.query("table_with_basic_data")
            else:
                # Second call
                return FakeResponse().get()
        elif database_id == "table_filter_call_new_data":
            if "filter" not in kwargs:
                # First call
                return self.query("table_with_basic_data")
            else:
                # Second call
                response = FakeResponse()
                response.add_element(my_title=title("Element 3"), price=number(-22))
                return response.get()
        elif database_id == "table_filter_call_updated_data":
            if "filter" not in kwargs:
                response = FakeResponse()
                response.add_element(my_title=title("Element 1"), price=number(56))
                response.add_element(my_title=title("Element 2"), price=number(98))
                # Fix the element ID to be able to modify it on second call
                response.query["results"][1]["id"] = "6c67da52-3a1b-4673-9d59-3e6cb94c142b"
                return response.get()
            else:
                response = FakeResponse()
                response.add_element(my_title=title("Element 2"), price=number(0))
                # Fix the element ID to be the same as the previous one
                response.query["results"][0]["id"] = "6c67da52-3a1b-4673-9d59-3e6cb94c142b"
                return response.get()
        elif database_id == "table_filter_call_crash_normal_call_updates":
            if "filter" not in kwargs:
                response = FakeResponse()
                # Depending on how many time we called this function, return different results
                if N_CALLS[database_id] == 1:
                    self.table_filter_call_crash_normal_call_updates_called = True
                    response.add_element(my_title=title("Element 1"), price=number(56))
                    response.add_element(my_title=title("Element 2"), price=number(98))
                else:
                    response.add_element(my_title=title("Element 1"), price=number(25))
                    response.add_element(my_title=title("Element 2"), price=number(51))
                return response.get()
            else:
                raise RuntimeError
        elif database_id == "table_filter_call_crash_normal_call_updates_2":
            # Same as table_filter_call_crash_normal_call_updates
            if "filter" not in kwargs:
                response = FakeResponse()
                if N_CALLS[database_id] == 1:
                    self.table_filter_call_crash_normal_call_updates_2_called = True
                    response.add_element(my_title=title("Element 1"), price=number(56))
                    response.add_element(my_title=title("Element 2"), price=number(98))
                else:
                    response.add_element(my_title=title("Element 1"), price=number(25))
                    response.add_element(my_title=title("Element 2"), price=number(51))
                return response.get()
            else:
                raise RuntimeError
        elif database_id == "table_call_crash":
            raise RuntimeError
        else:
            raise KeyError(f"{database_id} table query not implemented in Mock...")


class MockNotionClient:
    def __init__(self, auth: str):
        self.auth = auth
        self.databases = MockDBQuery()


# Monkey-patch !
notion_client.Client = MockNotionClient

import uuid
from collections import Counter
from typing import Dict, List, Union

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


def checkbox(x: bool) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "checkbox",
        "checkbox": x,
    }


def url(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "url",
        "url": x,
    }


def email(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "email",
        "email": x,
    }


def phone(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "phone_number",
        "phone_number": x,
    }


def formula(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "formula",
        "formula": {
            "type": "string",
            "string": x,
        },
    }


def relation() -> Dict:
    return {
        "id": "fF%3Ce",
        "has_more": False,
        "type": "relation",
        "relation": [{"id": "6f1f0aca-9999-4086-94fe-9dfe1d50ce43"}],
    }


def rollup() -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "rollup",
        "rollup": {
            "array": [],
            "function": "show_original",
            "type": "array",
        },
    }


def created_at(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "created_time",
        "created_time": x,
    }


def edited_at(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "last_edited_time",
        "last_edited_time": x,
    }


def created_by(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "created_by",
        "created_by": {
            "object": "user",
            "id": x,
        },
    }


def edited_by(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "last_edited_by",
        "last_edited_by": {
            "object": "user",
            "id": x,
        },
    }


def rich_text(text: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "rich_text",
        "rich_text": [
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


def select(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "select",
        "select": {"color": "green", "id": "d4fb0c3c-9999-453a-a5fc-6e560f101d63", "name": x},
    }


def multi_select(x: List[str]) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "multi_select",
        "multi_select": [{"color": "green", "id": "d4fb0c3c-9999-453a-a5fc-6e560f101d63", "name": t} for t in x],
    }


def status(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "status",
        "status": {"color": "default", "id": "d4fb0c3c-9999-453a-a5fc-6e560f101d63", "name": x},
    }


def date(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "date",
        "date": {
            "start": x,
            "end": None,
            "time_zone": None,
        },
    }


def people(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "people",
        "people": [
            {
                "id": x,
                "object": "user",
            }
        ],
    }


def files(x: str) -> Dict:
    return {
        "id": "fF%3Ce",
        "type": "files",
        "files": [
            {
                "name": x,
                "type": "file",
                "file": {
                    "expiry_time": "2023-05-07T15:10:11.829Z",
                    "url": "example.com",
                },
            }
        ],
    }


class QueryResponse:
    def __init__(self):
        self.res = {
            "object": "list",
            "results": [],
            "next_cursor": "None",
            "has_more": False,
            "type": "page",
            "page": {},
        }

    def add_element(self, **kwargs):
        self.res["results"].append(
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
        return self.res


class RetrieveResponse:
    def __init__(self):
        self.res = {
            "object": "database",
            "id": "bc1211ca-e3f1-4939-ae34-5260b16f627c",
            "created_time": "2021-07-08T23:50:00.000Z",
            "last_edited_time": "2021-07-08T23:50:00.000Z",
            "created_by": {"object": "user", "id": "9459043c-9999-4359-a430-c86902777967"},
            "last_edited_by": {"object": "user", "id": "9459043c-9999-4359-a430-c86902777967"},
            "icon": None,
            "cover": None,
            "url": "https://www.notion.so/bc1211cae3f14939ae34260b16f627c",
            "title": [],
            "description": [],
            "properties": {
                "created_at": {
                    "id": "fF%3Ce",
                    "name": "created_at",
                    "type": "created_time",
                    "created_time": {},
                },
                "status_attr": {
                    "id": "fF%3Ce",
                    "name": "status_attr",
                    "type": "status",
                    "status": {
                        "options": [
                            {
                                "id": "fF%3Ce",
                                "name": "Not started",
                                "color": "default",
                            },
                            {
                                "id": "fF%3C2",
                                "name": "In progress",
                                "color": "blue",
                            },
                        ],
                        "groups": [
                            {
                                "id": "fF%3Ce",
                                "name": "In Progress",
                                "color": "blue",
                                "option_ids": ["fF%3Ce", "fF%3C2"],
                            }
                        ],
                    },
                },
                "rich_text_attr": {
                    "id": "fF%3Ce",
                    "name": "rich_text_attr",
                    "type": "rich_text",
                    "rich_text": {},
                },
                "edited_at": {
                    "id": "fF%3Ce",
                    "name": "edited_at",
                    "type": "last_edited_time",
                    "last_edited_time": {},
                },
                "url_attr": {
                    "id": "fF%3Ce",
                    "name": "url_attr",
                    "type": "url",
                    "url": {},
                },
                "checkbox_attr": {
                    "id": "fF%3Ce",
                    "name": "checkbox_attr",
                    "type": "checkbox",
                    "checkbox": {},
                },
                "multi_select_attr": {
                    "id": "fF%3Ce",
                    "name": "multi_select_attr",
                    "type": "multi_select",
                    "multi_select": {
                        "options": [
                            {
                                "id": "fF%3Ce",
                                "name": "Opt1",
                                "color": "blue",
                            },
                            {
                                "id": "fF%3Ce",
                                "name": "Opt2",
                                "color": "purple",
                            },
                        ]
                    },
                },
                "select_attr": {
                    "id": "fF%3Ce",
                    "name": "select_attr",
                    "type": "select",
                    "select": {
                        "options": [
                            {
                                "id": "fF%3Ce",
                                "name": "Opt1",
                                "color": "blue",
                            },
                            {
                                "id": "fF%3Ce",
                                "name": "Opt2",
                                "color": "purple",
                            },
                        ]
                    },
                },
                "people_attr": {
                    "id": "fF%3Ce",
                    "name": "people_attr",
                    "type": "people",
                    "people": {},
                },
                "phone": {
                    "id": "fF%3Ce",
                    "name": "phone",
                    "type": "phone_number",
                    "phone_number": {},
                },
                "date_attr": {
                    "id": "fF%3Ce",
                    "name": "date_attr",
                    "type": "date",
                    "date": {},
                },
                "number_attr": {
                    "id": "fF%3Ce",
                    "name": "number_attr",
                    "type": "number",
                    "number": {
                        "format": "number",
                    },
                },
                "relation_attr": {
                    "id": "fF%3Ce",
                    "name": "relation_attr",
                    "type": "relation",
                    "relation": {
                        "database_id": "98ad959b-9999-4774-80ee-00246fb0ea9b",
                        "type": "single_property",
                        "single_property": {},
                    },
                },
                "created_by_attr": {
                    "id": "fF%3Ce",
                    "name": "created_by_attr",
                    "type": "created_by",
                    "created_by": {},
                },
                "edited_by": {
                    "id": "fF%3Ce",
                    "name": "edited_by",
                    "type": "last_edited_by",
                    "last_edited_by": {},
                },
                "email_attr": {
                    "id": "fF%3Ce",
                    "name": "email_attr",
                    "type": "email",
                    "email": {},
                },
                "files_attr": {
                    "id": "fF%3Ce",
                    "name": "files_attr",
                    "type": "files",
                    "files": {},
                },
                "formula_attr": {
                    "id": "fF%3Ce",
                    "name": "formula_attr",
                    "type": "formula",
                    "formula": {"expression": 'format(length(prop("number")))'},
                },
                "title_attr": {
                    "id": "fF%3Ce",
                    "name": "title_attr",
                    "type": "title",
                    "title": {},
                },
            },
            "parent": {"type": "page_id", "page_id": "98ad959b-9999-4774-80ee-00246fb0ea9b"},
            "archived": False,
            "is_inline": False,
        }

    def get(self):
        return self.res


# Global call counter, to know how many time each table is called through the Mock Notion API
N_CALLS = Counter()


class MockDBQuery:
    def query(self, database_id: str, **kwargs):  # noqa: C901
        N_CALLS[database_id] += 1
        if database_id == "table_with_basic_data":
            response = QueryResponse()
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
                return QueryResponse().get()
        elif database_id == "table_filter_call_new_data":
            if "filter" not in kwargs:
                # First call
                return self.query("table_with_basic_data")
            else:
                # Second call
                response = QueryResponse()
                response.add_element(my_title=title("Element 3"), price=number(-22))
                return response.get()
        elif database_id == "table_filter_call_updated_data":
            if "filter" not in kwargs:
                response = QueryResponse()
                response.add_element(my_title=title("Element 1"), price=number(56))
                response.add_element(my_title=title("Element 2"), price=number(98))
                # Fix the element ID to be able to modify it on second call
                response.res["results"][1]["id"] = "6c67da52-3a1b-4673-9d59-3e6cb94c142b"
                return response.get()
            else:
                response = QueryResponse()
                response.add_element(my_title=title("Element 2"), price=number(0))
                # Fix the element ID to be the same as the previous one
                response.res["results"][0]["id"] = "6c67da52-3a1b-4673-9d59-3e6cb94c142b"
                return response.get()
        elif database_id == "table_filter_call_crash_normal_call_updates":
            if "filter" not in kwargs:
                response = QueryResponse()
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
                response = QueryResponse()
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
        elif database_id == "table_full_data":
            response = QueryResponse()
            response.add_element(
                title=title("My title"),
                checkbox=checkbox(True),
                number=number(2.5),
                url=url("example.com"),
                email=email("me@example.com"),
                phone=phone("010-3715-6565"),
                formula=formula("256"),
                relation=relation(),
                rollup=rollup(),
                created_at=created_at("2023-05-07T14:02:00.000Z"),
                created_by=created_by("111"),
                edited_at=edited_at("2023-05-07T14:08:00.000Z"),
                edited_by=created_by("111"),
                rich_text=rich_text("Such a bore"),
                select=select("Option 1"),
                multi_select=multi_select(["Opt1", "Opt2"]),
                status=status("Not done"),
                date=date("2023-05-08T10:00:00.000+09:00"),
                people=people("111"),
                files=files("img.png"),
            )
            return response.get()
        else:
            raise KeyError(f"{database_id} table query not implemented in Mock...")

    def retrieve(self, database_id: str):
        if database_id == "table_schema_full_data":
            return RetrieveResponse().get()
        elif database_id == "table_with_basic_data":
            raise RuntimeError
        elif database_id == "table_api_error":
            raise notion_client.APIResponseError(httpx.Response(401), "", "")
        else:
            raise KeyError(f"{database_id} table query not implemented in Mock...")


class MockNotionClient:
    def __init__(self, auth: str):
        self.auth = auth
        self.databases = MockDBQuery()


# Monkey-patch !
notion_client.Client = MockNotionClient

"""A small in-memory RESTful API for tracking IOUs."""

import json


class RestAPI:
    def __init__(self, database=None):
        if database is None:
            database = {"users": []}
        if "users" not in database:
            database["users"] = []
        self.database = database

    @staticmethod
    def _parse_payload(payload):
        if payload is None:
            return {}
        if isinstance(payload, str):
            return json.loads(payload) or {}
        return payload or {}

    @staticmethod
    def _encode(data):
        return json.dumps(data)

    @staticmethod
    def _clean_amount(amount):
        amount = float(amount)
        return 0.0 if abs(amount) < 1e-12 else amount

    @classmethod
    def _balance_for(cls, user):
        owes = user.get("owes", {})
        owed_by = user.get("owed_by", {})
        return cls._clean_amount(sum(owed_by.values()) - sum(owes.values()))

    @classmethod
    def _public_user(cls, user):
        return {
            "name": user["name"],
            "owes": dict(user.get("owes", {})),
            "owed_by": dict(user.get("owed_by", {})),
            "balance": cls._balance_for(user),
        }

    @classmethod
    def _refresh_balance(cls, user):
        user["balance"] = cls._balance_for(user)

    def _named_users(self):
        return sorted(self.database["users"], key=lambda user: user["name"])

    def _find_user(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        raise KeyError("unknown user: {}".format(name))

    @staticmethod
    def _clear_pair(user, other_name):
        user.setdefault("owes", {}).pop(other_name, None)
        user.setdefault("owed_by", {}).pop(other_name, None)

    @classmethod
    def _existing_amount(cls, first_value, second_value):
        # owes/owed_by are redundant views of the same relationship.  Using
        # max() keeps a consistent database from being double counted while
        # still tolerating a one-sided relationship in supplied data.
        return max(float(first_value), float(second_value))

    def _record_iou(self, lender, borrower, amount):
        lender_name = lender["name"]
        borrower_name = borrower["name"]

        borrower_owes_lender = self._existing_amount(
            borrower.get("owes", {}).get(lender_name, 0.0),
            lender.get("owed_by", {}).get(borrower_name, 0.0),
        )
        lender_owes_borrower = self._existing_amount(
            lender.get("owes", {}).get(borrower_name, 0.0),
            borrower.get("owed_by", {}).get(lender_name, 0.0),
        )

        net = self._clean_amount(
            borrower_owes_lender - lender_owes_borrower + float(amount)
        )

        self._clear_pair(lender, borrower_name)
        self._clear_pair(borrower, lender_name)

        if net > 0:
            borrower["owes"][lender_name] = net
            lender["owed_by"][borrower_name] = net
        elif net < 0:
            lender["owes"][borrower_name] = -net
            borrower["owed_by"][lender_name] = -net

        self._refresh_balance(lender)
        self._refresh_balance(borrower)

    def get(self, url, payload=None):
        if url != "/users":
            raise ValueError("unsupported URL: {}".format(url))

        data = self._parse_payload(payload)
        requested = data.get("users")
        if requested is None:
            selected = self._named_users()
        else:
            wanted = set(requested)
            selected = [
                user for user in self._named_users() if user["name"] in wanted
            ]

        return self._encode({"users": [self._public_user(user) for user in selected]})

    def post(self, url, payload=None):
        data = self._parse_payload(payload)

        if url == "/add":
            user = {
                "name": data["user"],
                "owes": {},
                "owed_by": {},
                "balance": 0.0,
            }
            self.database["users"].append(user)
            return self._encode(self._public_user(user))

        if url == "/iou":
            lender = self._find_user(data["lender"])
            borrower = self._find_user(data["borrower"])
            self._record_iou(lender, borrower, data["amount"])

            affected = sorted((lender, borrower), key=lambda user: user["name"])
            return self._encode(
                {"users": [self._public_user(user) for user in affected]}
            )

        raise ValueError("unsupported URL: {}".format(url))

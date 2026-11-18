"""A small in-memory RESTful API for tracking IOUs."""


import json


class RestAPI:
    def __init__(self, database=None):
        if database is None:
            database = {"users": []}
        if "users" not in database:
            database["users"] = []
        self.database = database

    # ---------- public API ----------

    def get(self, url, payload=None):
        if url != "/users":
            raise ValueError(f"Unsupported GET URL: {url}")

        requested = None
        if payload is not None:
            data = self._decode_payload(payload)
            requested = set(data.get("users", []))

        users = self.database["users"]
        if requested is not None:
            users = [user for user in users if user["name"] in requested]

        return self._json({"users": self._sorted_users(users)})

    def post(self, url, payload=None):
        data = self._decode_payload(payload)

        if url == "/add":
            return self._add_user(data["user"])
        if url == "/iou":
            return self._create_iou(data["lender"], data["borrower"], data["amount"])
        raise ValueError(f"Unsupported POST URL: {url}")

    # ---------- operations ----------

    def _add_user(self, name):
        user = {
            "name": name,
            "owes": {},
            "owed_by": {},
            "balance": 0.0,
        }
        self.database["users"].append(user)
        return self._json(user)

    def _create_iou(self, lender_name, borrower_name, amount):
        lender = self._find_user(lender_name)
        borrower = self._find_user(borrower_name)

        # If the lender already owes the borrower, the new loan first cancels
        # that debt. Only the remainder creates a debt from borrower to lender.
        existing_debt = lender["owes"].get(borrower_name, 0)
        canceled = min(existing_debt, amount)

        if canceled:
            self._adjust_debt(lender, "owes", borrower_name, -canceled)
            self._adjust_debt(borrower, "owed_by", lender_name, -canceled)
            amount -= canceled

        if amount:
            self._adjust_debt(lender, "owed_by", borrower_name, amount)
            self._adjust_debt(borrower, "owes", lender_name, amount)

        self._recalculate_balance(lender)
        self._recalculate_balance(borrower)

        return self._json({"users": self._sorted_users([lender, borrower])})

    # ---------- helpers ----------

    @staticmethod
    def _decode_payload(payload):
        if payload is None:
            return {}
        if isinstance(payload, str):
            return json.loads(payload)
        if isinstance(payload, bytes):
            return json.loads(payload.decode("utf-8"))
        return payload

    @staticmethod
    def _json(value):
        return json.dumps(value)

    @staticmethod
    def _sorted_users(users):
        return sorted(users, key=lambda user: user["name"])

    def _find_user(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        raise ValueError(f"Unknown user: {name}")

    @staticmethod
    def _adjust_debt(user, field, other_name, delta):
        debts = user[field]
        new_amount = debts.get(other_name, 0) + delta
        if new_amount == 0:
            debts.pop(other_name, None)
        else:
            debts[other_name] = new_amount

    @staticmethod
    def _recalculate_balance(user):
        owed_to_user = sum(user["owed_by"].values())
        owed_by_user = sum(user["owes"].values())
        user["balance"] = owed_to_user - owed_by_user

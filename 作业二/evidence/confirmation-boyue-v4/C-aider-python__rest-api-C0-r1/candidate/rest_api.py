import json


class RestAPI:
    def __init__(self, database=None):
        self.database = database if database is not None else {"users": []}

    def get(self, url, payload=None):
        if url == "/users":
            return self._get_users(payload)
        raise ValueError("Unknown endpoint: " + url)

    def post(self, url, payload=None):
        if url == "/add":
            return self._add_user(json.loads(payload))
        if url == "/iou":
            return self._add_iou(json.loads(payload))
        raise ValueError("Unknown endpoint: " + url)

    def _get_users(self, payload):
        users = list(self.database["users"])
        if payload is not None:
            names = json.loads(payload)["users"]
            users = [user for user in users if user["name"] in names]
            users.sort(key=lambda user: user["name"])
        return json.dumps({"users": users})

    def _add_user(self, payload):
        user = {
            "name": payload["user"],
            "owes": {},
            "owed_by": {},
            "balance": 0.0,
        }
        self.database["users"].append(user)
        return json.dumps(user)

    def _add_iou(self, payload):
        lender = self._find_user(payload["lender"])
        borrower = self._find_user(payload["borrower"])
        amount = payload["amount"]

        # First cancel out any debt the lender already owes the borrower.
        if borrower["name"] in lender["owes"]:
            existing = lender["owes"][borrower["name"]]
            if existing <= amount:
                amount -= existing
                del lender["owes"][borrower["name"]]
                del borrower["owed_by"][lender["name"]]
            else:
                lender["owes"][borrower["name"]] = round(existing - amount, 2)
                borrower["owed_by"][lender["name"]] = round(existing - amount, 2)
                amount = 0.0

        # Register whatever remains as debt from borrower to lender.
        if amount > 0:
            lender["owed_by"].setdefault(borrower["name"], 0.0)
            borrower["owes"].setdefault(lender["name"], 0.0)
            lender["owed_by"][borrower["name"]] = round(
                lender["owed_by"][borrower["name"]] + amount, 2
            )
            borrower["owes"][lender["name"]] = round(
                borrower["owes"][lender["name"]] + amount, 2
            )

        self._update_balance(lender)
        self._update_balance(borrower)

        response_users = sorted([lender, borrower], key=lambda user: user["name"])
        return json.dumps({"users": response_users})

    def _find_user(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        raise KeyError("User not found: " + name)

    @staticmethod
    def _update_balance(user):
        user["balance"] = round(
            sum(user["owed_by"].values()) - sum(user["owes"].values()), 2
        )

import json


class RestAPI:
    def __init__(self, database=None):
        self.database = database if database is not None else {"users": []}
        self.database.setdefault("users", [])

    def _all_users(self):
        return self.database["users"]

    def _find_user(self, name):
        for user in self._all_users():
            if user["name"] == name:
                return user
        return None

    @staticmethod
    def _recalculate_balance(user):
        user["balance"] = round(
            sum(user["owed_by"].values()) - sum(user["owes"].values()), 10
        )

    def get(self, url, payload=None):
        if url == "/users":
            users = self._all_users()
            if payload is not None:
                requested = json.loads(payload).get("users", [])
                users = [user for user in users if user["name"] in requested]
            return json.dumps({"users": sorted(users, key=lambda user: user["name"])})
        return json.dumps({"users": []})

    def post(self, url, payload=None):
        if url == "/add":
            data = json.loads(payload)
            name = data["user"]
            existing = self._find_user(name)
            if existing is not None:
                return json.dumps(existing)
            new_user = {
                "name": name,
                "owes": {},
                "owed_by": {},
                "balance": 0.0,
            }
            self._all_users().append(new_user)
            return json.dumps(new_user)

        if url == "/iou":
            data = json.loads(payload)
            lender = self._find_user(data["lender"])
            borrower = self._find_user(data["borrower"])
            amount = float(data["amount"])

            # Net relationship between the two users: a positive value means
            # the borrower owes the lender.
            net = round(
                lender["owed_by"].get(borrower["name"], 0.0)
                - lender["owes"].get(borrower["name"], 0.0)
                + amount,
                10,
            )

            lender["owed_by"].pop(borrower["name"], None)
            lender["owes"].pop(borrower["name"], None)
            borrower["owed_by"].pop(lender["name"], None)
            borrower["owes"].pop(lender["name"], None)

            if net > 0:
                lender["owed_by"][borrower["name"]] = net
                borrower["owes"][lender["name"]] = net
            elif net < 0:
                lender["owes"][borrower["name"]] = -net
                borrower["owed_by"][lender["name"]] = -net

            self._recalculate_balance(lender)
            self._recalculate_balance(borrower)

            return json.dumps(
                {"users": sorted([lender, borrower], key=lambda user: user["name"])}
            )

        return json.dumps({})

import copy
import json


class RestAPI:
    def __init__(self, database=None):
        if database is None:
            database = {"users": []}
        self.database = copy.deepcopy(database)
        self.users = {
            user["name"]: copy.deepcopy(user)
            for user in self.database.get("users", [])
        }
        for user in self.users.values():
            user.setdefault("owes", {})
            user.setdefault("owed_by", {})
            user["balance"] = self._balance(user)

    @staticmethod
    def _parse(payload):
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        return json.loads(payload)

    @staticmethod
    def _balance(user):
        owes = user.get("owes", {})
        owed_by = user.get("owed_by", {})
        return float(sum(owed_by.values()) - sum(owes.values()))

    def _user_response(self, name):
        user = self.users[name]
        return {
            "name": user["name"],
            "owes": dict(user["owes"]),
            "owed_by": dict(user["owed_by"]),
            "balance": self._balance(user),
        }

    def _sync_database(self):
        self.database["users"] = [
            self._user_response(name) for name in sorted(self.users)
        ]

    def get(self, url, payload=None):
        data = self._parse(payload)
        if url == "/users":
            names = data.get("users")
            if names is None:
                names = sorted(self.users)
            users = [
                self._user_response(name)
                for name in sorted(names)
                if name in self.users
            ]
            return json.dumps({"users": users})
        return json.dumps({})

    def post(self, url, payload=None):
        data = self._parse(payload)
        if url == "/add":
            name = data["user"]
            self.users[name] = {
                "name": name,
                "owes": {},
                "owed_by": {},
                "balance": 0.0,
            }
            self._sync_database()
            return json.dumps(self._user_response(name))

        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])

            lender_user = self.users[lender]
            borrower_user = self.users[borrower]

            borrower_owes_lender = borrower_user["owes"].get(lender, 0.0)
            lender_owes_borrower = lender_user["owes"].get(borrower, 0.0)
            net = borrower_owes_lender + amount - lender_owes_borrower

            lender_user["owes"].pop(borrower, None)
            lender_user["owed_by"].pop(borrower, None)
            borrower_user["owes"].pop(lender, None)
            borrower_user["owed_by"].pop(lender, None)

            if abs(net) > 1e-12:
                if net > 0:
                    borrower_user["owes"][lender] = net
                    lender_user["owed_by"][borrower] = net
                else:
                    lender_user["owes"][borrower] = -net
                    borrower_user["owed_by"][lender] = -net

            lender_user["balance"] = self._balance(lender_user)
            borrower_user["balance"] = self._balance(borrower_user)
            self._sync_database()

            return json.dumps({
                "users": [
                    self._user_response(name)
                    for name in sorted([lender, borrower])
                ]
            })

        return json.dumps({})

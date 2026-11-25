import json


class RestAPI:
    def __init__(self, database=None):
        database = database or {"users": []}
        self.users = {}
        for user in database.get("users", []):
            name = user["name"]
            self.users[name] = {
                "name": name,
                "owes": dict(user.get("owes", {})),
                "owed_by": dict(user.get("owed_by", {})),
            }
        for name in self.users:
            self._recompute(name)

    def _recompute(self, name):
        user = self.users[name]
        user["balance"] = round(
            sum(user["owed_by"].values()) - sum(user["owes"].values()), 2
        )

    def _user_object(self, name):
        user = self.users[name]
        return {
            "name": name,
            "owes": dict(user["owes"]),
            "owed_by": dict(user["owed_by"]),
            "balance": user["balance"],
        }

    def get(self, url, payload=None):
        if url != "/users":
            raise ValueError("Unknown url: {}".format(url))

        data = self._decode(payload)
        if data and "users" in data:
            names = sorted(data["users"])
            users = [self._user_object(n) for n in names if n in self.users]
        else:
            users = [self._user_object(n) for n in sorted(self.users)]
        return json.dumps({"users": users})

    def post(self, url, payload=None):
        data = self._decode(payload)

        if url == "/add":
            name = data["user"]
            self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
            self._recompute(name)
            return json.dumps(self._user_object(name))

        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])
            self._record_iou(lender, borrower, amount)
            names = sorted([lender, borrower])
            return json.dumps({"users": [self._user_object(n) for n in names]})

        raise ValueError("Unknown url: {}".format(url))

    def _record_iou(self, lender, borrower, amount):
        lender_user = self.users[lender]
        borrower_user = self.users[borrower]

        # Positive means the borrower owes the lender; negative means the reverse.
        outstanding = (
            borrower_user["owes"].get(lender, 0.0)
            - lender_user["owes"].get(borrower, 0.0)
        )
        outstanding = round(outstanding + amount, 2)

        lender_user["owes"].pop(borrower, None)
        borrower_user["owed_by"].pop(lender, None)
        borrower_user["owes"].pop(lender, None)
        lender_user["owed_by"].pop(borrower, None)

        if outstanding > 0:
            borrower_user["owes"][lender] = outstanding
            lender_user["owed_by"][borrower] = outstanding
        elif outstanding < 0:
            lender_user["owes"][borrower] = -outstanding
            borrower_user["owed_by"][lender] = -outstanding

        self._recompute(lender)
        self._recompute(borrower)

    @staticmethod
    def _decode(payload):
        if payload is None:
            return {}
        if isinstance(payload, str):
            return json.loads(payload) if payload.strip() else {}
        return payload

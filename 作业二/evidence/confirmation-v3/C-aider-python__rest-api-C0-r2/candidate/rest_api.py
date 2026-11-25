import json


class RestAPI:
    def __init__(self, database=None):
        self.users = {}
        for user in (database or {}).get("users", []):
            name = user["name"]
            self.users[name] = {
                "name": name,
                "owes": dict(user.get("owes", {})),
                "owed_by": dict(user.get("owed_by", {})),
            }

    @staticmethod
    def _clean(mapping):
        return {
            name: amount
            for name, amount in sorted(mapping.items())
            if round(amount, 2) != 0
        }

    def _balance(self, name):
        user = self.users[name]
        total_owed_by = sum(user["owed_by"].values())
        total_owed_to = sum(user["owes"].values())
        return round(total_owed_by - total_owed_to, 2)

    def _user_object(self, name):
        user = self.users[name]
        return {
            "name": name,
            "owes": self._clean(user["owes"]),
            "owed_by": self._clean(user["owed_by"]),
            "balance": float(self._balance(name)),
        }

    def _record_iou(self, lender, borrower, amount):
        lender_user = self.users[lender]
        borrower_user = self.users[borrower]

        # How much the lender already owes the borrower.
        existing = lender_user["owes"].get(borrower, 0.0)
        net = round(amount - existing, 2)

        if net > 0:
            # The old debt is fully cancelled; the borrower now owes the rest.
            lender_user["owes"].pop(borrower, None)
            borrower_user["owed_by"].pop(lender, None)
            borrower_user["owes"][lender] = round(
                borrower_user["owes"].get(lender, 0.0) + net, 2
            )
            lender_user["owed_by"][borrower] = round(
                lender_user["owed_by"].get(borrower, 0.0) + net, 2
            )
        elif net < 0:
            # The lender still owes the borrower the difference.
            remaining = round(-net, 2)
            lender_user["owes"][borrower] = remaining
            borrower_user["owed_by"][lender] = remaining
        else:
            lender_user["owes"].pop(borrower, None)
            borrower_user["owed_by"].pop(lender, None)

    def get(self, url, payload=None):
        if url == "/users":
            names = None
            if payload:
                names = json.loads(payload).get("users")
            if names is None:
                names = list(self.users)
            return json.dumps(
                {"users": [self._user_object(name) for name in sorted(names)]}
            )
        raise ValueError("Unknown url: {}".format(url))

    def post(self, url, payload=None):
        data = json.loads(payload) if payload else {}
        if url == "/add":
            name = data["user"]
            self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
            return json.dumps(self._user_object(name))
        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])
            self._record_iou(lender, borrower, amount)
            return json.dumps(
                {
                    "users": [
                        self._user_object(name)
                        for name in sorted([lender, borrower])
                    ]
                }
            )
        raise ValueError("Unknown url: {}".format(url))

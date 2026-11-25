import json


class RestAPI:
    def __init__(self, database=None):
        self.users = {}
        database = database or {}
        for user in database.get("users", []):
            name = user["name"]
            self.users[name] = {
                "name": name,
                "owes": {k: round(float(v), 2) for k, v in (user.get("owes") or {}).items() if v},
                "owed_by": {k: round(float(v), 2) for k, v in (user.get("owed_by") or {}).items() if v},
            }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _balance(user):
        total = sum(user["owed_by"].values()) - sum(user["owes"].values())
        return round(total, 2)

    def _serialize(self, user):
        return {
            "name": user["name"],
            "owes": dict(user["owes"]),
            "owed_by": dict(user["owed_by"]),
            "balance": self._balance(user),
        }

    def _set_debt(self, debtor, creditor, amount):
        """Make `debtor` owe `creditor` exactly `amount` (0 removes the entry)."""
        amount = round(amount, 2)
        if amount > 0:
            debtor["owes"][creditor["name"]] = amount
            creditor["owed_by"][debtor["name"]] = amount
        else:
            debtor["owes"].pop(creditor["name"], None)
            creditor["owed_by"].pop(debtor["name"], None)

    def get(self, url, payload=None):
        if url == "/users":
            names = None
            if payload:
                data = json.loads(payload) if isinstance(payload, str) else payload
                names = data.get("users")
            if names is None:
                selected = sorted(self.users)
            else:
                selected = sorted(n for n in names if n in self.users)
            return json.dumps({"users": [self._serialize(self.users[n]) for n in selected]})
        raise ValueError("Unknown url: {}".format(url))

    def post(self, url, payload=None):
        data = payload
        if isinstance(data, str):
            data = json.loads(data)
        data = data or {}

        if url == "/add":
            name = data["user"]
            self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
            return json.dumps(self._serialize(self.users[name]))

        if url == "/iou":
            lender = self.users[data["lender"]]
            borrower = self.users[data["borrower"]]
            amount = round(float(data["amount"]), 2)

            # Net the new loan against whatever is already owed between the pair.
            already = round(borrower["owes"].get(lender["name"], 0.0)
                            - lender["owes"].get(borrower["name"], 0.0), 2)
            net = round(already + amount, 2)  # how much borrower now owes lender

            if net >= 0:
                self._set_debt(borrower, lender, net)
                self._set_debt(lender, borrower, 0)
            else:
                self._set_debt(lender, borrower, -net)
                self._set_debt(borrower, lender, 0)

            result = [self._serialize(lender), self._serialize(borrower)]
            result.sort(key=lambda u: u["name"])
            return json.dumps({"users": result})

        raise ValueError("Unknown url: {}".format(url))

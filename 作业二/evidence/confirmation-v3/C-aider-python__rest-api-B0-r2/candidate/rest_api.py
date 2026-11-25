import json


class RestAPI:
    def __init__(self, database=None):
        self.users = {}
        if database:
            for user in database.get("users", []):
                self.users[user["name"]] = {
                    "name": user["name"],
                    "owes": dict(user.get("owes", {})),
                    "owed_by": dict(user.get("owed_by", {})),
                    "balance": float(user.get("balance", 0.0)),
                }

    def _ledger(self):
        ledger = {name: {} for name in self.users}
        for name, user in self.users.items():
            for other, amount in user["owes"].items():
                ledger.setdefault(name, {})
                ledger[name][other] = ledger[name].get(other, 0.0) + amount
                ledger.setdefault(other, {})
        return ledger

    def _normalize(self, ledger):
        for name, user in self.users.items():
            owes = {}
            owed_by = {}
            for other in self.users:
                if other == name:
                    continue
                net = round(
                    ledger.get(name, {}).get(other, 0.0)
                    - ledger.get(other, {}).get(name, 0.0),
                    2,
                )
                if net > 0:
                    owes[other] = net
                elif net < 0:
                    owed_by[other] = -net
            user["owes"] = dict(sorted(owes.items()))
            user["owed_by"] = dict(sorted(owed_by.items()))
            user["balance"] = round(
                sum(user["owed_by"].values()) - sum(user["owes"].values()), 2
            )

    def get(self, url, payload=None):
        if url == "/users":
            names = sorted(self.users)
            if payload:
                requested = json.loads(payload).get("users")
                if requested is not None:
                    wanted = set(requested)
                    names = [name for name in names if name in wanted]
            return json.dumps({"users": [self.users[name] for name in names]})
        raise ValueError("Unknown URL: {}".format(url))

    def post(self, url, payload=None):
        data = json.loads(payload) if payload else {}

        if url == "/add":
            name = data["user"]
            self.users[name] = {
                "name": name,
                "owes": {},
                "owed_by": {},
                "balance": 0.0,
            }
            return json.dumps(self.users[name])

        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = data["amount"]

            ledger = self._ledger()
            ledger.setdefault(borrower, {})
            ledger[borrower][lender] = ledger[borrower].get(lender, 0.0) + amount
            self._normalize(ledger)

            names = sorted({lender, borrower})
            return json.dumps({"users": [self.users[name] for name in names]})

        raise ValueError("Unknown URL: {}".format(url))

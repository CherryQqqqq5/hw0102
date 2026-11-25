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
                }

    def _user_object(self, name):
        user = self.users[name]
        owes = {k: v for k, v in user["owes"].items() if v != 0}
        owed_by = {k: v for k, v in user["owed_by"].items() if v != 0}
        balance = float(round(float(sum(owed_by.values())) - float(sum(owes.values())), 2))
        return {"name": name, "owes": owes, "owed_by": owed_by, "balance": balance}

    def _adjust(self, debtor, creditor, amount):
        """Record that `debtor` owes `creditor` `amount` more than before.

        A negative amount means the creditor actually owes the debtor.
        """
        d = self.users[debtor]
        c = self.users[creditor]
        current = d["owes"].get(creditor, 0.0) - d["owed_by"].get(creditor, 0.0)
        new = round(current + amount, 2)

        if new > 0:
            d["owes"][creditor] = new
            d["owed_by"].pop(creditor, None)
            c["owed_by"][debtor] = new
            c["owes"].pop(debtor, None)
        elif new < 0:
            d["owed_by"][creditor] = -new
            d["owes"].pop(creditor, None)
            c["owes"][debtor] = -new
            c["owed_by"].pop(debtor, None)
        else:
            d["owes"].pop(creditor, None)
            d["owed_by"].pop(creditor, None)
            c["owes"].pop(debtor, None)
            c["owed_by"].pop(debtor, None)

    def get(self, url, payload=None):
        if url == "/users":
            data = {}
            if payload:
                data = json.loads(payload) if isinstance(payload, str) else payload
            if data.get("users"):
                names = [name for name in data["users"] if name in self.users]
            else:
                names = list(self.users)
            users = [self._user_object(name) for name in names]
            users.sort(key=lambda user: user["name"])
            return json.dumps({"users": users})
        return json.dumps({})

    def post(self, url, payload=None):
        data = json.loads(payload) if isinstance(payload, str) else (payload or {})
        if url == "/add":
            name = data["user"]
            self.users.setdefault(
                name, {"name": name, "owes": {}, "owed_by": {}}
            )
            return json.dumps(self._user_object(name))
        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = data["amount"]
            self._adjust(borrower, lender, amount)
            users = [self._user_object(lender), self._user_object(borrower)]
            users.sort(key=lambda user: user["name"])
            return json.dumps({"users": users})
        return json.dumps({})

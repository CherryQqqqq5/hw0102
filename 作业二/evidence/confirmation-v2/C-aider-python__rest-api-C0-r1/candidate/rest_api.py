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

    def _balance(self, name):
        user = self.users[name]
        return round(sum(user["owed_by"].values()) - sum(user["owes"].values()), 2)

    def _user_obj(self, name):
        user = self.users[name]
        return {
            "name": name,
            "owes": dict(user["owes"]),
            "owed_by": dict(user["owed_by"]),
            "balance": self._balance(name),
        }

    def get(self, url, payload=None):
        if url == "/users":
            names = sorted(self.users)
            if payload:
                requested = json.loads(payload).get("users")
                if requested is not None:
                    names = sorted(n for n in requested if n in self.users)
            return json.dumps({"users": [self._user_obj(n) for n in names]})
        return json.dumps({})

    def post(self, url, payload=None):
        data = json.loads(payload) if payload else {}
        if url == "/add":
            name = data["user"]
            self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
            return json.dumps(self._user_obj(name))
        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])
            self._apply_iou(lender, borrower, amount)
            names = sorted([lender, borrower])
            return json.dumps({"users": [self._user_obj(n) for n in names]})
        return json.dumps({})

    def _apply_iou(self, lender, borrower, amount):
        l_user = self.users[lender]
        b_user = self.users[borrower]
        # Net position: (already owed by borrower to lender) - (already owed by lender to borrower)
        existing_borrower_owes = b_user["owes"].get(lender, 0.0)
        existing_lender_owes = l_user["owes"].get(borrower, 0.0)
        net = round(existing_borrower_owes - existing_lender_owes + amount, 2)
        # Clear both existing directions before re-adding the netted debt.
        b_user["owes"].pop(lender, None)
        l_user["owed_by"].pop(borrower, None)
        l_user["owes"].pop(borrower, None)
        b_user["owed_by"].pop(lender, None)
        if net > 0:
            self._add_debt(borrower, lender, net)
        elif net < 0:
            self._add_debt(lender, borrower, -net)

    def _add_debt(self, debtor, creditor, amount):
        d = self.users[debtor]
        c = self.users[creditor]
        d["owes"][creditor] = round(d["owes"].get(creditor, 0.0) + amount, 2)
        c["owed_by"][debtor] = round(c["owed_by"].get(debtor, 0.0) + amount, 2)

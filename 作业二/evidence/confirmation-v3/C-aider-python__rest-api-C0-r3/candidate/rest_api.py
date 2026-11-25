import json


def _round(value):
    value = round(value, 2)
    # Avoid returning -0.0
    return 0.0 if value == 0 else value


class RestAPI:
    def __init__(self, database=None):
        database = database or {"users": []}
        self.users = {}
        for user in database.get("users", []):
            self.users[user["name"]] = {
                "name": user["name"],
                "owes": {k: float(v) for k, v in user.get("owes", {}).items()},
                "owed_by": {k: float(v) for k, v in user.get("owed_by", {}).items()},
            }

    def _user_object(self, name):
        user = self.users[name]
        owes = {k: _round(v) for k, v in sorted(user["owes"].items()) if _round(v) != 0}
        owed_by = {
            k: _round(v) for k, v in sorted(user["owed_by"].items()) if _round(v) != 0
        }
        balance = _round(sum(owed_by.values()) - sum(owes.values()))
        return {"name": name, "owes": owes, "owed_by": owed_by, "balance": balance}

    def _users_response(self, names=None):
        if names is None:
            names = self.users.keys()
        return {"users": [self._user_object(n) for n in sorted(names)]}

    def get(self, url, payload=None):
        if url == "/users":
            names = None
            if payload is not None:
                data = json.loads(payload) if isinstance(payload, str) else payload
                names = data.get("users") if data else None
            return json.dumps(self._users_response(names))
        raise ValueError("Unknown URL: {}".format(url))

    def post(self, url, payload=None):
        data = json.loads(payload) if isinstance(payload, str) else (payload or {})

        if url == "/add":
            name = data["user"]
            if name not in self.users:
                self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
            return json.dumps(self._user_object(name))

        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])
            self._apply_iou(lender, borrower, amount)
            return json.dumps(self._users_response([lender, borrower]))

        raise ValueError("Unknown URL: {}".format(url))

    def _apply_iou(self, lender, borrower, amount):
        lender_user = self.users[lender]
        borrower_user = self.users[borrower]

        # Net amount currently owed by borrower to lender (positive) or
        # by lender to borrower (negative).
        net = lender_user["owed_by"].get(borrower, 0.0) - lender_user["owes"].get(
            borrower, 0.0
        )
        net = _round(net + amount)

        lender_user["owes"].pop(borrower, None)
        lender_user["owed_by"].pop(borrower, None)
        borrower_user["owes"].pop(lender, None)
        borrower_user["owed_by"].pop(lender, None)

        if net > 0:
            lender_user["owed_by"][borrower] = net
            borrower_user["owes"][lender] = net
        elif net < 0:
            lender_user["owes"][borrower] = -net
            borrower_user["owed_by"][lender] = -net

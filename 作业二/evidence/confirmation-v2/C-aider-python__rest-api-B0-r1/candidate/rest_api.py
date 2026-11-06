import json


class RestAPI:
    def __init__(self, database=None):
        database = database or {"users": []}
        self.users = {}
        for user in database.get("users", []):
            self.users[user["name"]] = {
                "name": user["name"],
                "owes": dict(user.get("owes", {})),
                "owed_by": dict(user.get("owed_by", {})),
            }

    def _clean(self, mapping):
        return {name: value for name, value in mapping.items() if round(value, 2) != 0}

    def _user_object(self, name):
        user = self.users[name]
        owes = {k: round(v, 2) for k, v in self._clean(user["owes"]).items()}
        owed_by = {k: round(v, 2) for k, v in self._clean(user["owed_by"]).items()}
        balance = round(sum(owed_by.values()) - sum(owes.values()), 2)
        return {
            "name": name,
            "owes": owes,
            "owed_by": owed_by,
            "balance": balance,
        }

    def _add_user(self, name):
        if name not in self.users:
            self.users[name] = {"name": name, "owes": {}, "owed_by": {}}
        return self.users[name]

    def get(self, url, payload=None):
        if url != "/users":
            raise ValueError("Unknown URL: {}".format(url))

        if payload:
            names = json.loads(payload).get("users")
        else:
            names = None

        if names is None:
            selected = sorted(self.users)
        else:
            selected = sorted(names)

        return json.dumps({"users": [self._user_object(name) for name in selected]})

    def post(self, url, payload=None):
        data = json.loads(payload) if payload else {}

        if url == "/add":
            name = data["user"]
            self._add_user(name)
            return json.dumps(self._user_object(name))

        if url == "/iou":
            lender = self._add_user(data["lender"])
            borrower = self._add_user(data["borrower"])
            amount = data["amount"]

            lender_name = lender["name"]
            borrower_name = borrower["name"]

            # net > 0 means the lender is owed by the borrower
            net = borrower["owes"].get(lender_name, 0.0) - lender["owes"].get(borrower_name, 0.0)
            net = round(net + amount, 2)

            lender["owes"].pop(borrower_name, None)
            lender["owed_by"].pop(borrower_name, None)
            borrower["owes"].pop(lender_name, None)
            borrower["owed_by"].pop(lender_name, None)

            if net > 0:
                lender["owed_by"][borrower_name] = net
                borrower["owes"][lender_name] = net
            elif net < 0:
                lender["owes"][borrower_name] = -net
                borrower["owed_by"][lender_name] = -net

            names = sorted([lender_name, borrower_name])
            return json.dumps({"users": [self._user_object(name) for name in names]})

        raise ValueError("Unknown URL: {}".format(url))

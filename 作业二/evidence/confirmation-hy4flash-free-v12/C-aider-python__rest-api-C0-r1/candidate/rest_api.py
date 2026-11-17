import json


class RestAPI:
    def __init__(self, database=None):
        self.database = {"users": []} if database is None else database
        self.database.setdefault("users", [])

    @staticmethod
    def _decode(payload):
        if payload is None:
            return {}
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode()
        if isinstance(payload, str):
            return json.loads(payload) if payload.strip() else {}
        return payload

    @staticmethod
    def _clean(amounts):
        for name in list(amounts):
            if not amounts[name]:
                del amounts[name]

    @staticmethod
    def _clear_pair(first, second):
        first_name = first["name"]
        second_name = second["name"]
        first["owes"].pop(second_name, None)
        second["owed_by"].pop(first_name, None)
        second["owes"].pop(first_name, None)
        first["owed_by"].pop(second_name, None)

    @staticmethod
    def _assign_debt(debtor, creditor, amount):
        amount = float(amount)
        if amount <= 0:
            debtor["owes"].pop(creditor["name"], None)
            creditor["owed_by"].pop(debtor["name"], None)
        else:
            debtor["owes"][creditor["name"]] = amount
            creditor["owed_by"][debtor["name"]] = amount

    @staticmethod
    def _update_balance(user):
        user["balance"] = float(
            sum(float(v) for v in user["owed_by"].values())
            - sum(float(v) for v in user["owes"].values())
        )

    def _selected_users(self, names):
        users = self.database["users"]
        if names is None:
            selected = users
        else:
            wanted = set(names)
            selected = [user for user in users if user["name"] in wanted]
        return sorted(selected, key=lambda user: user["name"])

    def get(self, url, payload=None):
        data = self._decode(payload)
        if url == "/users":
            return json.dumps({"users": self._selected_users(data.get("users"))})
        raise ValueError("Unsupported GET URL: {}".format(url))

    def post(self, url, payload=None):
        data = self._decode(payload)
        if url == "/add":
            user = {"name": data["user"], "owes": {}, "owed_by": {}, "balance": 0.0}
            self.database["users"].append(user)
            return json.dumps(user)

        if url == "/iou":
            lender_name = data["lender"]
            borrower_name = data["borrower"]
            amount = float(data["amount"])

            users = {user["name"]: user for user in self.database["users"]}
            lender = users[lender_name]
            borrower = users[borrower_name]

            for user in (lender, borrower):
                self._clean(user["owes"])
                self._clean(user["owed_by"])

            borrower_owes_lender = float(borrower["owes"].get(lender_name, 0.0))
            lender_owes_borrower = float(lender["owes"].get(borrower_name, 0.0))
            net = borrower_owes_lender - lender_owes_borrower + amount

            self._clear_pair(lender, borrower)
            if net > 0:
                self._assign_debt(borrower, lender, net)
            elif net < 0:
                self._assign_debt(lender, borrower, -net)

            self._update_balance(lender)
            self._update_balance(borrower)
            return json.dumps({"users": sorted((lender, borrower), key=lambda user: user["name"])})

        raise ValueError("Unsupported POST URL: {}".format(url))

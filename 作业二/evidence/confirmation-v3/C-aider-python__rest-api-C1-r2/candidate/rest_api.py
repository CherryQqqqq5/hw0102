import json


def _clean(x):
    """Round away floating-point noise, collapsing near-zero to 0.0."""
    x = round(float(x), 10)
    if abs(x) < 1e-9:
        return 0.0
    return x


class RestAPI:
    def __init__(self, database=None):
        database = database or {"users": []}
        # _net[a][b] = signed amount b owes a (positive => b owes a).
        # Invariant: _net[a][b] == -_net[b][a].
        self._net = {}
        users = database.get("users", [])
        for user in users:
            self._net.setdefault(user["name"], {})

        recorded = set()

        def set_net(a, b, amount):
            self._net.setdefault(a, {})
            self._net.setdefault(b, {})
            self._net[a][b] = _clean(self._net[a].get(b, 0.0) + amount)
            self._net[b][a] = _clean(self._net[b].get(a, 0.0) - amount)
            recorded.add((a, b))
            recorded.add((b, a))

        for user in users:
            name = user["name"]
            for other, amount in user.get("owes", {}).items():
                if (name, other) in recorded:
                    continue
                # name owes other => other is owed +amount
                set_net(other, name, _clean(amount))

        for user in users:
            name = user["name"]
            for other, amount in user.get("owed_by", {}).items():
                if (name, other) in recorded:
                    continue
                # other owes name
                set_net(name, other, _clean(amount))

    def _user_object(self, name):
        owes = {}
        owed_by = {}
        for other, net in self._net.get(name, {}).items():
            net = _clean(net)
            if net > 0:
                owed_by[other] = net
            elif net < 0:
                owes[other] = _clean(-net)
        balance = _clean(sum(owed_by.values()) - sum(owes.values()))
        return {
            "name": name,
            "owes": owes,
            "owed_by": owed_by,
            "balance": balance,
        }

    def _update_pair(self, a, b, amount):
        """Record that b owes a `amount` more (signed)."""
        self._net.setdefault(a, {})
        self._net.setdefault(b, {})
        self._net[a][b] = _clean(self._net[a].get(b, 0.0) + amount)
        self._net[b][a] = _clean(self._net[b].get(a, 0.0) - amount)

    def get(self, url, payload=None):
        if url == "/users":
            if payload:
                data = json.loads(payload) if isinstance(payload, str) else payload
                names = data.get("users", [])
                users = [self._user_object(n) for n in sorted(names)]
            else:
                users = [self._user_object(n) for n in sorted(self._net)]
            return json.dumps({"users": users})
        raise ValueError("Unknown url: %s" % url)

    def post(self, url, payload=None):
        data = json.loads(payload) if isinstance(payload, str) else (payload or {})
        if url == "/add":
            name = data["user"]
            self._net.setdefault(name, {})
            return json.dumps(self._user_object(name))
        if url == "/iou":
            lender = data["lender"]
            borrower = data["borrower"]
            amount = float(data["amount"])
            self._net.setdefault(lender, {})
            self._net.setdefault(borrower, {})
            # Borrower now owes lender `amount` more.
            self._update_pair(lender, borrower, amount)
            return json.dumps(
                {"users": [self._user_object(n) for n in sorted([lender, borrower])]}
            )
        raise ValueError("Unknown url: %s" % url)

class Record:
    def __init__(self, record_id, parent_id):
        self.record_id = record_id
        self.parent_id = parent_id


class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []


def BuildTree(records):
    if not records:
        return None

    records.sort(key=lambda record: record.record_id)

    for expected_id, record in enumerate(records):
        if record.record_id != expected_id:
            raise ValueError("Record id is invalid or out of order.")

    nodes = {}
    root = None

    for record in records:
        node = Node(record.record_id)

        if record.record_id == 0:
            if record.parent_id != 0:
                raise ValueError(
                    "Node parent_id should be smaller than it's record_id."
                )
            root = node
        else:
            if record.record_id == record.parent_id:
                raise ValueError(
                    "Only root should have equal record and parent id."
                )
            if record.parent_id > record.record_id:
                raise ValueError(
                    "Node parent_id should be smaller than it's record_id."
                )
            nodes[record.parent_id].children.append(node)

        nodes[record.record_id] = node

    return root

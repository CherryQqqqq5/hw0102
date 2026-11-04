"""Basic list operations implemented from scratch (no built-ins used)."""


def append(list1, list2):
    if not list1:
        return list2
    return [list1[0]] + append(list1[1:], list2)


def concat(lists):
    if not lists:
        return []
    return append(lists[0], concat(lists[1:]))


def filter(function, list):
    if not list:
        return []
    if function(list[0]):
        return [list[0]] + filter(function, list[1:])
    return filter(function, list[1:])


def length(list):
    if not list:
        return 0
    return 1 + length(list[1:])


def map(function, list):
    if not list:
        return []
    return [function(list[0])] + map(function, list[1:])


def foldl(function, list, initial):
    if not list:
        return initial
    return foldl(function, list[1:], function(initial, list[0]))


def foldr(function, list, initial):
    if not list:
        return initial
    return function(foldr(function, list[1:], initial), list[0])


def reverse(list):
    if not list:
        return []
    return append(reverse(list[1:]), [list[0]])

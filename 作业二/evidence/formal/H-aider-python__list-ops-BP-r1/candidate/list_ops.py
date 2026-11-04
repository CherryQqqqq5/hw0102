def append(list1, list2):
    result = []
    for item in list1:
        result = result + [item]
    for item in list2:
        result = result + [item]
    return result


def concat(lists):
    result = []
    for sublist in lists:
        for item in sublist:
            result = result + [item]
    return result


def filter(function, list):
    result = []
    for item in list:
        if function(item):
            result = result + [item]
    return result


def length(list):
    count = 0
    for _ in list:
        count += 1
    return count


def map(function, list):
    result = []
    for item in list:
        result = result + [function(item)]
    return result


def foldl(function, list, initial):
    accumulator = initial
    for item in list:
        accumulator = function(accumulator, item)
    return accumulator


def foldr(function, list, initial):
    accumulator = initial
    index = 0
    for _ in list:
        index += 1
    while index > 0:
        index -= 1
        accumulator = function(accumulator, list[index])
    return accumulator


def reverse(list):
    result = []
    index = 0
    for _ in list:
        index += 1
    while index > 0:
        index -= 1
        result = result + [list[index]]
    return result

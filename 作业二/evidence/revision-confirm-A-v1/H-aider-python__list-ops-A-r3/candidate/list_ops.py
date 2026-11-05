def _foldl(function, sequence, initial):
    accumulator = initial
    for item in sequence:
        accumulator = function(accumulator, item)
    return accumulator


def _reverse(sequence):
    result = []
    for item in sequence:
        result = [item] + result
    return result


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
        count = count + 1
    return count


def map(function, list):
    result = []
    for item in list:
        result = result + [function(item)]
    return result


def foldl(function, list, initial):
    return _foldl(function, list, initial)


def foldr(function, list, initial):
    return _foldl(function, _reverse(list), initial)


def reverse(list):
    return _reverse(list)

def append(list1, list2):
    return list1 + list2


def concat(lists):
    result = []
    for sublist in lists:
        result = append(result, sublist)
    return result


def filter(function, list):
    result = []
    for item in list:
        if function(item):
            result = append(result, [item])
    return result


def length(list):
    count = 0
    for _ in list:
        count += 1
    return count


def map(function, list):
    result = []
    for item in list:
        result = append(result, [function(item)])
    return result


def foldl(function, list, initial):
    accumulator = initial
    for item in list:
        accumulator = function(accumulator, item)
    return accumulator


def foldr(function, list, initial):
    accumulator = initial
    for item in reverse(list):
        accumulator = function(accumulator, item)
    return accumulator


def reverse(list):
    result = []
    for item in list:
        result = [item] + result
    return result

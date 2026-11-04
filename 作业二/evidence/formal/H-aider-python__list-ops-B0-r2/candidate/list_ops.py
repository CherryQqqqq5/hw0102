def append(list1, list2):
    """Return a new list with all items of list2 added to the end of list1."""
    result = list2
    for item in reverse(list1):
        result = [item] + result
    return result


def concat(lists):
    """Flatten a series of lists into one list (one level deep)."""
    result = []
    for sublist in lists:
        result = append(result, sublist)
    return result


def filter(function, list):
    """Return the items of list for which function(item) is true."""
    result = []
    for item in list:
        if function(item):
            result = append(result, [item])
    return result


def length(list):
    """Return the number of items in list."""
    count = 0
    for _ in list:
        count += 1
    return count


def map(function, list):
    """Return the list of results of applying function to every item."""
    result = []
    for item in list:
        result = append(result, [function(item)])
    return result


def foldl(function, list, initial):
    """Fold each item into the accumulator, from the left."""
    accumulator = initial
    for item in list:
        accumulator = function(accumulator, item)
    return accumulator


def foldr(function, list, initial):
    """Fold each item into the accumulator, from the right."""
    accumulator = initial
    index = length(list) - 1
    while index >= 0:
        accumulator = function(accumulator, list[index])
        index -= 1
    return accumulator


def reverse(list):
    """Return a list with the same items in reversed order."""
    result = []
    for item in list:
        result = [item] + result
    return result

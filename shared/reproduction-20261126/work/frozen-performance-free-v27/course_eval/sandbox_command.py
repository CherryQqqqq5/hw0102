# 嵌套 timeout 会建立独立进程组，逐个终止后代可避免输出管道遗留。
CONTAINER_COMMAND = """
terminate_tree() {
    local pid=$1 children_file children child
    kill -STOP "$pid" 2>/dev/null || return 0
    for children_file in /proc/"$pid"/task/*/children; do
        children=$(<"$children_file") 2>/dev/null || continue
        for child in $children; do
            terminate_tree "$child"
        done
    done
    kill -KILL "$pid" 2>/dev/null || :
}
expire() {
    terminate_tree "$command_pid"
    wait "$command_pid" 2>/dev/null
    exit 124
}
trap expire USR1
bash -c "$1" &
command_pid=$!
wait "$command_pid"
"""

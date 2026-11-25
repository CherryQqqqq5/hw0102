/// Transform each element of the input vector by applying the given function.
pub fn map<F, T, U>(input: Vec<T>, mut function: F) -> Vec<U>
where
    F: FnMut(T) -> U,
{
    let mut output = Vec::with_capacity(input.len());
    for item in input {
        output.push(function(item));
    }
    output
}

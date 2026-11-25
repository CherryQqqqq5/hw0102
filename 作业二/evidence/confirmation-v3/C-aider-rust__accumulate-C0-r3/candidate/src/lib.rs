/// Apply `function` to each element of `input`, collecting the results.
pub fn map<T, U, F>(input: Vec<T>, mut function: F) -> Vec<U>
where
    F: FnMut(T) -> U,
{
    let mut output = Vec::with_capacity(input.len());
    for item in input {
        output.push(function(item));
    }
    output
}

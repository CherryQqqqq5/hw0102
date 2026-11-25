/// Apply `function` to every element of `input`, returning a new vector of
/// the results. Implemented without using iterator `map`/`collect`.
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

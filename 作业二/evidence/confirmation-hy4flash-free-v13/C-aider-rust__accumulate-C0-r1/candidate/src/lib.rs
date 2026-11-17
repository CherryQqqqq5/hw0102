/// Apply `function` to every element of `input`, returning a new vector.
pub fn map<T, U, F>(input: Vec<T>, mut function: F) -> Vec<U>
where
    F: FnMut(T) -> U,
{
    let mut output = Vec::with_capacity(input.len());
    for element in input {
        output.push(function(element));
    }
    output
}

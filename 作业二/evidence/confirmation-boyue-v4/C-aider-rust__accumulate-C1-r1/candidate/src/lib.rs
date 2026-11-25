/// Apply `function` to every element of `input` and return the results.
///
/// This is implemented manually (without `Iterator::map`/`collect`) as
/// required by the exercise.
pub fn map<T, U, F>(input: Vec<T>, mut function: F) -> Vec<U>
where
    F: FnMut(T) -> U,
{
    let mut output = Vec::with_capacity(input.len());
    for value in input {
        output.push(function(value));
    }
    output
}

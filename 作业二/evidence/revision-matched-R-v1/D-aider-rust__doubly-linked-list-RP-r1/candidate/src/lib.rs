// this module adds some functionality based on the required implementations
// here like: `LinkedList::pop_back` or `Clone for LinkedList<T>`
// You are free to use anything in it, but it's mainly for the test framework.
mod pre_implemented;

use std::marker::PhantomData;
use std::ptr::NonNull;

type Link<T> = Option<NonNull<Node<T>>>;

struct Node<T> {
    next: Link<T>,
    prev: Link<T>,
    element: T,
}

/// A doubly linked list.
///
/// Safety invariants:
/// - `front` points to the first node and `back` to the last node, and both are
///   `None` exactly when the list is empty.
/// - Every node is uniquely owned by the list and is reachable from either
///   `front` or `back` through the node links.
/// - For adjacent nodes `a` and `b`, `a.next == Some(b)` iff `b.prev == Some(a)`.
/// - `len` is always the exact number of nodes in the list.
pub struct LinkedList<T> {
    front: Link<T>,
    back: Link<T>,
    len: usize,
    // Covariant over T and records that the list owns T values.
    _marker: PhantomData<T>,
}

pub struct Cursor<'a, T> {
    list: &'a mut LinkedList<T>,
    current: Link<T>,
}

pub struct Iter<'a, T> {
    current: Link<T>,
    _marker: PhantomData<&'a T>,
}

// SAFETY: A LinkedList owns all of its T values. Sending the list to another
// thread transfers that ownership, so it is safe exactly when T is Send.
unsafe impl<T: Send> Send for LinkedList<T> {}

// SAFETY: A shared LinkedList only permits shared access to its T values, so it
// is safe to share exactly when T is Sync.
unsafe impl<T: Sync> Sync for LinkedList<T> {}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        Self {
            front: None,
            back: None,
            len: 0,
            _marker: PhantomData,
        }
    }

    // You may be wondering why it's necessary to have is_empty()
    // when it can easily be determined from len().
    // It's good custom to have both because len() can be expensive for some types,
    // whereas is_empty() is almost always cheap.
    // (Also ask yourself whether len() is expensive for LinkedList)
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    pub fn len(&self) -> usize {
        self.len
    }

    /// Return a cursor positioned on the front element
    pub fn cursor_front(&mut self) -> Cursor<'_, T> {
        Cursor {
            current: self.front,
            list: self,
        }
    }

    /// Return a cursor positioned on the back element
    pub fn cursor_back(&mut self) -> Cursor<'_, T> {
        Cursor {
            current: self.back,
            list: self,
        }
    }

    /// Return an iterator that moves from front to back
    pub fn iter(&self) -> Iter<'_, T> {
        Iter {
            current: self.front,
            _marker: PhantomData,
        }
    }
}

// the cursor is expected to act as if it is at the position of an element
// and it also has to work with and be able to insert into an empty list.
impl<T> Cursor<'_, T> {
    /// Take a mutable reference to the current element
    pub fn peek_mut(&mut self) -> Option<&mut T> {
        // SAFETY: `current` is either `None` or a pointer to a live node owned
        // by `self.list`. The cursor has exclusive access to the list through
        // `&mut self`, so no aliasing mutable reference can exist.
        unsafe { self.current.map(|node| &mut (*node.as_ptr()).element) }
    }

    /// Move one position forward (towards the back) and
    /// return a reference to the new position
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&mut T> {
        // SAFETY: `current` is either `None` or a valid node pointer. Its
        // `next` pointer is either `None` or points to another node owned by
        // the same list. The exclusive list borrow prevents aliasing.
        unsafe {
            let current = self.current?;
            let next = (*current.as_ptr()).next?;
            self.current = Some(next);
            Some(&mut (*next.as_ptr()).element)
        }
    }

    /// Move one position backward (towards the front) and
    /// return a reference to the new position
    pub fn prev(&mut self) -> Option<&mut T> {
        // SAFETY: symmetric to `next`: `prev` is either `None` or points to a
        // valid node in this exclusively borrowed list.
        unsafe {
            let current = self.current?;
            let prev = (*current.as_ptr()).prev?;
            self.current = Some(prev);
            Some(&mut (*prev.as_ptr()).element)
        }
    }

    /// Remove and return the element at the current position and move the cursor
    /// to the neighboring element that's closest to the back. This can be
    /// either the next or previous position.
    pub fn take(&mut self) -> Option<T> {
        // SAFETY: `current` is a live node owned by the list. We unlink it from
        // its neighbors, fix up the list endpoints and length, and then reclaim
        // the box. `Box::from_raw` receives a pointer that came from `Box::leak`
        // and has not been freed yet; after unlinking, the list no longer owns
        // this node, so reclaiming it is sound.
        unsafe {
            let node = self.current?;
            let node_ptr = node.as_ptr();
            let next = (*node_ptr).next;
            let prev = (*node_ptr).prev;

            match prev {
                Some(prev) => (*prev.as_ptr()).next = next,
                None => self.list.front = next,
            }
            match next {
                Some(next) => (*next.as_ptr()).prev = prev,
                None => self.list.back = prev,
            }

            self.current = next.or(prev);
            self.list.len -= 1;

            // Move the element out of the node, then let the box deallocate
            // the now element-less node storage.
            let Node { element, .. } = *Box::from_raw(node_ptr);
            Some(element)
        }
    }

    pub fn insert_after(&mut self, element: T) {
        // SAFETY: `current`, if present, is a valid node owned by the list. The
        // new node is heap-allocated and immediately linked into the list. All
        // stored pointers are either from live allocations or existing nodes.
        unsafe {
            let new = NonNull::from(Box::leak(Box::new(Node {
                next: None,
                prev: None,
                element,
            })));

            match self.current {
                Some(current) => {
                    let current_ptr = current.as_ptr();
                    let next = (*current_ptr).next;

                    (*new.as_ptr()).prev = Some(current);
                    (*new.as_ptr()).next = next;
                    (*current_ptr).next = Some(new);

                    match next {
                        Some(next) => (*next.as_ptr()).prev = Some(new),
                        None => self.list.back = Some(new),
                    }
                }
                None => {
                    // The list is empty: the new node is both front and back,
                    // and the cursor now points at it.
                    self.list.front = Some(new);
                    self.list.back = Some(new);
                    self.current = Some(new);
                }
            }

            self.list.len += 1;
        }
    }

    pub fn insert_before(&mut self, element: T) {
        // SAFETY: symmetric to `insert_after`.
        unsafe {
            let new = NonNull::from(Box::leak(Box::new(Node {
                next: None,
                prev: None,
                element,
            })));

            match self.current {
                Some(current) => {
                    let current_ptr = current.as_ptr();
                    let prev = (*current_ptr).prev;

                    (*new.as_ptr()).next = Some(current);
                    (*new.as_ptr()).prev = prev;
                    (*current_ptr).prev = Some(new);

                    match prev {
                        Some(prev) => (*prev.as_ptr()).next = Some(new),
                        None => self.list.front = Some(new),
                    }
                }
                None => {
                    self.list.front = Some(new);
                    self.list.back = Some(new);
                    self.current = Some(new);
                }
            }

            self.list.len += 1;
        }
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<Self::Item> {
        // SAFETY: every pointer held by the iterator is either `None` or points
        // to a live node in the list borrowed for `'a`. The list is immutably
        // borrowed for the iterator's lifetime, so no mutation can invalidate
        // these pointers or alias the returned references.
        unsafe {
            let current = self.current?;
            self.current = (*current.as_ptr()).next;
            Some(&(*current.as_ptr()).element)
        }
    }
}

impl<T> Drop for LinkedList<T> {
    fn drop(&mut self) {
        let mut current = self.front;
        while let Some(node) = current {
            // SAFETY: each node is owned by the list and is visited exactly
            // once. We read the next link before deallocating the current node.
            unsafe {
                let boxed = Box::from_raw(node.as_ptr());
                current = boxed.next;
                // `boxed` is dropped here, deallocating the node and dropping
                // its element.
            }
        }
    }
}

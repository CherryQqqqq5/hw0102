// this module adds some functionality based on the required implementations
// here like: `LinkedList::pop_back` or `Clone for LinkedList<T>`
// You are free to use anything in it, but it's mainly for the test framework.
mod pre_implemented;

use std::marker::PhantomData;
use std::ptr::NonNull;

/// A single node of a [`LinkedList`].
///
/// A node is allocated on the heap as a `Box<Node<T>>`. The list that
/// allocated a node is its unique owner and is responsible for freeing it:
/// either when the node is unlinked (by turning the raw pointer back into a
/// `Box`), or in `LinkedList::drop`.
struct Node<T> {
    next: Option<NonNull<Node<T>>>,
    prev: Option<NonNull<Node<T>>>,
    element: T,
}

impl<T> Node<T> {
    fn new(element: T) -> Self {
        Node {
            next: None,
            prev: None,
            element,
        }
    }
}

/// A doubly linked list.
///
/// # Invariants
///
/// * `head` points to the first node, `tail` to the last node. Both are `None`
///   exactly when `len == 0`.
/// * Every node reachable from `head`/`tail` is a live allocation owned by
///   exactly this list; no node is reachable from two lists and no node is
///   reachable twice from the same list (it is acyclic).
/// * For every linked node `n`: `n.next.map(|x| x.prev) == Some(n)` and
///   `n.prev.map(|x| x.next) == Some(n)`. `head.prev` and `tail.next` are
///   `None`.
/// * `len` is the number of nodes reachable from `head` (equivalently from
///   `tail`).
pub struct LinkedList<T> {
    head: Option<NonNull<Node<T>>>,
    tail: Option<NonNull<Node<T>>>,
    len: usize,
    /// `PhantomData<T>` tells the compiler that the list owns `T` values (for
    /// drop-check and auto-trait purposes). Because it holds no actual `T`, it
    /// also keeps `LinkedList<T>` *covariant* over `T`.
    marker: PhantomData<T>,
}

/// A cursor pointing at a position inside a [`LinkedList`].
///
/// # Invariants
///
/// * `current` is either `None` or points to a live node owned by `list`.
/// * If `list` is non-empty then `current` is `Some`. It is `None` only for an
///   empty list (the cursor is then conceptually "between" the two ends, which
///   is where insertions go).
pub struct Cursor<'a, T> {
    list: &'a mut LinkedList<T>,
    current: Option<NonNull<Node<T>>>,
}

/// An iterator over the elements of a [`LinkedList`] from front to back.
///
/// `PhantomData<&'a T>` keeps it covariant over `T` (and over `'a`).
pub struct Iter<'a, T> {
    head: Option<NonNull<Node<T>>>,
    marker: PhantomData<&'a T>,
}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        LinkedList {
            head: None,
            tail: None,
            len: 0,
            marker: PhantomData,
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
            current: self.head,
            list: self,
        }
    }

    /// Return a cursor positioned on the back element
    pub fn cursor_back(&mut self) -> Cursor<'_, T> {
        Cursor {
            current: self.tail,
            list: self,
        }
    }

    /// Return an iterator that moves from front to back
    pub fn iter(&self) -> Iter<'_, T> {
        Iter {
            head: self.head,
            marker: PhantomData,
        }
    }
}

impl<T> Default for LinkedList<T> {
    fn default() -> Self {
        Self::new()
    }
}

// the cursor is expected to act as if it is at the position of an element
// and it also has to work with and be able to insert into an empty list.
impl<T> Cursor<'_, T> {
    /// Take a mutable reference to the current element
    pub fn peek_mut(&mut self) -> Option<&mut T> {
        // SAFETY: if `current` is `Some` it points to a live node owned by
        // `self.list` (cursor invariant). We hold a unique borrow of the list
        // for `'_`, so no other reference into the list can exist, and the
        // returned reference cannot outlive the borrow of `self`.
        self.current
            .map(|node| unsafe { &mut (*node.as_ptr()).element })
    }

    /// Move one position forward (towards the back) and
    /// return a reference to the new position
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&mut T> {
        // SAFETY: `current` points to a live node of the list, so reading its
        // `next` pointer is valid. It is either `None` or a live node of the
        // same list (invariant).
        let next = unsafe { (*self.current?.as_ptr()).next };
        match next {
            Some(next) => {
                self.current = Some(next);
                // SAFETY: `next` is a live node owned by `self.list`, and the
                // borrow rules of `&mut self` guarantee exclusive access.
                Some(unsafe { &mut (*next.as_ptr()).element })
            }
            // Already at the back; the cursor stays on the current element so
            // that `insert_after` still has a position to work with.
            None => None,
        }
    }

    /// Move one position backward (towards the front) and
    /// return a reference to the new position
    pub fn prev(&mut self) -> Option<&mut T> {
        // SAFETY: `current` points to a live node of the list, so reading its
        // `prev` pointer is valid. It is either `None` or a live node of the
        // same list (invariant).
        let prev = unsafe { (*self.current?.as_ptr()).prev };
        match prev {
            Some(prev) => {
                self.current = Some(prev);
                // SAFETY: `prev` is a live node owned by `self.list`, and the
                // borrow rules of `&mut self` guarantee exclusive access.
                Some(unsafe { &mut (*prev.as_ptr()).element })
            }
            // Already at the front; stay put (see `next`).
            None => None,
        }
    }

    /// Remove and return the element at the current position and move the cursor
    /// to the neighboring element that's closest to the back. This can be
    /// either the next or previous position.
    pub fn take(&mut self) -> Option<T> {
        let node = self.current?;
        // SAFETY: `node` points to a live node owned by `self.list`, so all of
        // its fields may be read. Because the list owns that node, we are
        // allowed to take the `Box` back and free it, provided we unlink it
        // from its neighbours first. `self` holds a unique borrow of the list,
        // so no other reference to any node exists.
        unsafe {
            let next = (*node.as_ptr()).next;
            let prev = (*node.as_ptr()).prev;

            // Unlink the node (maintaining the doubly linked invariants).
            match prev {
                Some(prev) => (*prev.as_ptr()).next = next,
                None => self.list.head = next,
            }
            match next {
                Some(next) => (*next.as_ptr()).prev = prev,
                None => self.list.tail = prev,
            }
            self.list.len -= 1;

            // Move to the neighbour closest to the back: the next one if it
            // exists, otherwise the previous one.
            self.current = next.or(prev);

            // SAFETY: the node is no longer reachable from the list (we just
            // unlinked it), it was allocated with `Box::into_raw(Box::new(..))`
            // with the same layout, and it is freed exactly once here.
            Some(Box::from_raw(node.as_ptr()).element)
        }
    }

    pub fn insert_after(&mut self, element: T) {
        // SAFETY: `Box::into_raw` hands the allocation over to us; it is
        // immediately re-registered (below) into a list that owns it.
        let node = unsafe { NonNull::new_unchecked(Box::into_raw(Box::new(Node::new(element)))) };

        match self.current {
            Some(current) => {
                // SAFETY: `current` is a live node of the list. `node` is a
                // fresh allocation that is not yet linked, so linking it here
                // keeps the list's invariants intact.
                unsafe {
                    let next = (*current.as_ptr()).next;
                    (*current.as_ptr()).next = Some(node);
                    (*node.as_ptr()).prev = Some(current);
                    (*node.as_ptr()).next = next;
                    match next {
                        Some(next) => (*next.as_ptr()).prev = Some(node),
                        None => self.list.tail = Some(node),
                    }
                }
                // The cursor deliberately stays on `current`: inserting
                // repeatedly after the same position therefore builds the
                // elements in reverse order (matching the expected semantics).
            }
            None => {
                // The list is empty (cursor invariant): the new node becomes
                // both ends and the cursor points at it.
                debug_assert!(self.list.head.is_none() && self.list.tail.is_none());
                // No unsafe needed: with an empty list there are no links to
                // repair, and the fresh node simply becomes the whole list.
                self.list.head = Some(node);
                self.list.tail = Some(node);
                self.current = Some(node);
            }
        }
        self.list.len += 1;
    }

    pub fn insert_before(&mut self, element: T) {
        // SAFETY: see `insert_after`; the allocation is owned by the list as
        // soon as it is linked below.
        let node = unsafe { NonNull::new_unchecked(Box::into_raw(Box::new(Node::new(element)))) };

        match self.current {
            Some(current) => {
                // SAFETY: `current` is a live node of the list and `node` is a
                // fresh, unlinked allocation, so splicing it in preserves the
                // list's invariants.
                unsafe {
                    let prev = (*current.as_ptr()).prev;
                    (*current.as_ptr()).prev = Some(node);
                    (*node.as_ptr()).next = Some(current);
                    (*node.as_ptr()).prev = prev;
                    match prev {
                        Some(prev) => (*prev.as_ptr()).next = Some(node),
                        None => self.list.head = Some(node),
                    }
                }
                // The cursor stays on `current`, so repeated insertions before
                // it keep their order.
            }
            None => {
                // The list is empty (cursor invariant): the new node becomes
                // both ends and the cursor points at it.
                debug_assert!(self.list.head.is_none() && self.list.tail.is_none());
                // No unsafe needed: with an empty list there are no links to
                // repair, and the fresh node simply becomes the whole list.
                self.list.head = Some(node);
                self.list.tail = Some(node);
                self.current = Some(node);
            }
        }
        self.list.len += 1;
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<&'a T> {
        let node = self.head?;
        // SAFETY: `node` points to a live node of the list (list invariant).
        // The iterator borrows the list for `'a`, so no node can be removed or
        // mutated for as long as the yielded references live; `next` is read
        // before any reference is handed out.
        unsafe {
            self.head = (*node.as_ptr()).next;
            Some(&(*node.as_ptr()).element)
        }
    }
}

impl<T> Drop for LinkedList<T> {
    fn drop(&mut self) {
        let mut current = self.head.take();
        while let Some(node) = current {
            // SAFETY: every node reachable from `head` is owned by this list,
            // so each one must be freed exactly once. We read `next` before
            // freeing the node it belongs to, and the node was allocated with
            // `Box::into_raw(Box::new(..))` with the same layout.
            unsafe {
                current = (*node.as_ptr()).next;
                drop(Box::from_raw(node.as_ptr()));
            }
        }
        self.tail = None;
        self.len = 0;
    }
}

// SAFETY: sending a `LinkedList<T>` to another thread transfers ownership of
// all of its `T` elements, which is sound exactly when `T: Send`. The raw
// pointers themselves are only ever dereferenced by the owner of the list.
unsafe impl<T: Send> Send for LinkedList<T> {}

// SAFETY: `&LinkedList<T>` only hands out `&T` (via `iter`, `front`, `back`),
// so it is safe to share across threads exactly when `T: Sync`.
unsafe impl<T: Sync> Sync for LinkedList<T> {}

#[cfg(feature = "advanced")]
const _: () = {
    // Only compiled with `advanced`: documents that the manual impls above are
    // the only reason `LinkedList` is conditionally `Send`/`Sync`.
};

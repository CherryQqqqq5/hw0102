// this module adds some functionality based on the required implementations
// here like: `LinkedList::pop_back` or `Clone for LinkedList<T>`
// You are free to use anything in it, but it's mainly for the test framework.
mod pre_implemented;

use std::marker::PhantomData;
use std::ptr::NonNull;

// ---------------------------------------------------------------------------
// Safety-critical invariants for the whole module
//
// (1) Every node is created through `LinkedList::boxed_node` (i.e. it lives in a
//     heap allocation owned by exactly one list) and is freed exactly once:
//     either by `LinkedList::unlink_node` or by `Drop for LinkedList`.
// (2) For every live node, `prev` and `next` are either `None` or point to live
//     nodes of the very same list; together the nodes form one consistent
//     doubly linked chain from `front` to `back`.
// (3) `front`'s `prev` is `None`, `back`'s `next` is `None`, and `len` is the
//     number of nodes reachable from `front`.
// (4) Access to the nodes is only handed out through borrowed views of the list:
//     `Cursor` borrows the list mutably, `Iter` immutably. Hence no node ever
//     has an aliasing `&mut`/`&` pair, and no reference outlives the list borrow.
// ---------------------------------------------------------------------------

/// A single list node.
struct Node<T> {
    data: T,
    next: Option<NonNull<Node<T>>>,
    prev: Option<NonNull<Node<T>>>,
}

/// A doubly linked list.
///
/// `front`/`back`/`next`/`prev` are `NonNull` raw pointers, which are covariant
/// over `T`, so the whole structure is covariant over `T` (see invariant (4) of
/// the module docs, and `advanced_is_covariant` test).
pub struct LinkedList<T> {
    front: Option<NonNull<Node<T>>>,
    back: Option<NonNull<Node<T>>>,
    len: usize,
    /// Declares that the list logically owns `T`s (covariant in `T`).
    marker: PhantomData<T>,
}

/// A cursor over a list, always positioned on an element (or on nothing, which
/// means "the list is empty").
pub struct Cursor<'a, T> {
    list: &'a mut LinkedList<T>,
    current: Option<NonNull<Node<T>>>,
}

/// An iterator over `&T`, moving from front to back.
pub struct Iter<'a, T> {
    next: Option<NonNull<Node<T>>>,
    /// Covariant over both `'a` and `T`, tying the yielded references to `'a`.
    marker: PhantomData<&'a T>,
}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        Self {
            front: None,
            back: None,
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

    /// For our list `len()` is O(1): the length is stored in the list itself.
    pub fn len(&self) -> usize {
        self.len
    }

    /// Return a cursor positioned on the front element
    pub fn cursor_front(&mut self) -> Cursor<'_, T> {
        let current = self.front;
        Cursor { list: self, current }
    }

    /// Return a cursor positioned on the back element
    pub fn cursor_back(&mut self) -> Cursor<'_, T> {
        let current = self.back;
        Cursor { list: self, current }
    }

    /// Return an iterator that moves from front to back
    pub fn iter(&self) -> Iter<'_, T> {
        Iter {
            next: self.front,
            marker: PhantomData,
        }
    }

    /// Allocates a fresh node on the heap and returns a pointer to it.
    ///
    /// The returned node is unlinked (`prev == next == None`) and is not yet
    /// reachable from any list, so the caller owns it until it is linked in.
    fn boxed_node(data: T) -> NonNull<Node<T>> {
        let node = Box::new(Node {
            data,
            next: None,
            prev: None,
        });
        // SAFETY: `Box::into_raw` never returns a null pointer.
        unsafe { NonNull::new_unchecked(Box::into_raw(node)) }
    }

    /// Unlinks `node` from this list, deallocates it and returns its data.
    ///
    /// # Safety
    ///
    /// - `node` must be a non-null pointer to a node allocated by
    ///   `LinkedList::boxed_node`.
    /// - The node must still be owned by `self` (linked into this list) and must
    ///   not be referenced by any other pointer that is used after this call.
    /// - The caller must have exclusive access to the list, so that updating the
    ///   neighbours' links cannot race with or invalidate other references.
    unsafe fn unlink_node(&mut self, node: NonNull<Node<T>>) -> T {
        // SAFETY: the caller guarantees the pointer was produced by `Box::into_raw`
        // in `boxed_node` and is still owned (not yet freed) by this list, so
        // taking ownership of the allocation is valid and happens exactly once.
        let node = unsafe { Box::from_raw(node.as_ptr()) };

        // Relink the neighbours around the node (invariant (2)). Only live nodes
        // are touched: siblings are still owned by the list.
        match node.prev {
            // SAFETY: `prev` points to a live node of this list (invariant (2));
            // we have exclusive access to it through `&mut self`.
            Some(prev) => unsafe { (*prev.as_ptr()).next = node.next },
            None => self.front = node.next,
        }
        match node.next {
            // SAFETY: `next` points to a live node of this list (invariant (2));
            // we have exclusive access to it through `&mut self`.
            Some(next) => unsafe { (*next.as_ptr()).prev = node.prev },
            None => self.back = node.prev,
        }

        self.len -= 1;
        node.data
    }
}

impl<T> Default for LinkedList<T> {
    fn default() -> Self {
        Self::new()
    }
}

// The cursor is expected to act as if it is at the position of an element
// and it also has to work with and be able to insert into an empty list.
impl<T> Cursor<'_, T> {
    /// Take a mutable reference to the current element
    pub fn peek_mut(&mut self) -> Option<&mut T> {
        let current = self.current?;
        // SAFETY: `current` points to a node owned by the borrowed list (invariant
        // (1)/(2)), and `self` holds the only mutable borrow of that list, so no
        // other reference to `data` exists (invariant (4)).
        unsafe { Some(&mut (*current.as_ptr()).data) }
    }

    /// Move one position forward (towards the back) and
    /// return a reference to the new position
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&mut T> {
        let current = self.current?;
        // SAFETY: `current` is a node owned by the list; reading its `next` link
        // yields `None` or another live node of the same list (invariant (2)).
        let next = unsafe { (*current.as_ptr()).next };
        self.current = next;
        self.peek_mut()
    }

    /// Move one position backward (towards the front) and
    /// return a reference to the new position
    pub fn prev(&mut self) -> Option<&mut T> {
        let current = self.current?;
        // SAFETY: `current` is a node owned by the list; reading its `prev` link
        // yields `None` or another live node of the same list (invariant (2)).
        let prev = unsafe { (*current.as_ptr()).prev };
        self.current = prev;
        self.peek_mut()
    }

    /// Remove and return the element at the current position and move the cursor
    /// to the neighboring element that's closest to the back. This can be
    /// either the next or previous position.
    pub fn take(&mut self) -> Option<T> {
        let current = self.current?;
        // SAFETY: `current` is a live node of the list, so its links are `None` or
        // point to live nodes of the same list (invariant (2)). We read them
        // before the node is freed below.
        let (next, prev) = unsafe {
            let node = &*current.as_ptr();
            (node.next, node.prev)
        };

        // A removed node's `next` (if any) survives the removal, otherwise the
        // node before the removed one becomes the new position.
        self.current = next.or(prev);

        // SAFETY: `current` is owned by `self.list` and this cursor is its only
        // accessor, so unlinking (which frees the node) is allowed and the
        // pointer is not used afterwards.
        Some(unsafe { self.list.unlink_node(current) })
    }

    pub fn insert_after(&mut self, element: T) {
        let new_node = LinkedList::<T>::boxed_node(element);
        match self.current {
            Some(current) => {
                // SAFETY: `current` is a node owned by the list and `new_node` was
                // just allocated, so it is not aliased. Mutating the links keeps
                // invariants (2) and (3).
                unsafe {
                    let current_ref = &mut *current.as_ptr();
                    let old_next = current_ref.next;
                    {
                        let new_ref = &mut *new_node.as_ptr();
                        new_ref.prev = Some(current);
                        new_ref.next = old_next;
                    }
                    current_ref.next = Some(new_node);
                    match old_next {
                        Some(next) => (*next.as_ptr()).prev = Some(new_node),
                        None => self.list.back = Some(new_node),
                    }
                }
                self.list.len += 1;
            }
            None => {
                // The cursor has no element only when the list is empty.
                debug_assert!(self.list.is_empty());
                self.list.front = Some(new_node);
                self.list.back = Some(new_node);
                self.list.len = 1;
                self.current = Some(new_node);
            }
        }
    }

    pub fn insert_before(&mut self, element: T) {
        let new_node = LinkedList::<T>::boxed_node(element);
        match self.current {
            Some(current) => {
                // SAFETY: `current` is a node owned by the list and `new_node` was
                // just allocated, so it is not aliased. Mutating the links keeps
                // invariants (2) and (3).
                unsafe {
                    let current_ref = &mut *current.as_ptr();
                    let old_prev = current_ref.prev;
                    {
                        let new_ref = &mut *new_node.as_ptr();
                        new_ref.next = Some(current);
                        new_ref.prev = old_prev;
                    }
                    current_ref.prev = Some(new_node);
                    match old_prev {
                        Some(prev) => (*prev.as_ptr()).next = Some(new_node),
                        None => self.list.front = Some(new_node),
                    }
                }
                self.list.len += 1;
            }
            None => {
                // The cursor has no element only when the list is empty.
                debug_assert!(self.list.is_empty());
                self.list.front = Some(new_node);
                self.list.back = Some(new_node);
                self.list.len = 1;
                self.current = Some(new_node);
            }
        }
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<&'a T> {
        let node = self.next?;
        // SAFETY: the iterator borrows the list for `'a`, so all of its nodes stay
        // alive and unchanged for `'a` (nothing can obtain `&mut` to the list
        // while this `&'a LinkedList` borrow exists). The yielded reference thus
        // lives for `'a` and does not alias any `&mut`.
        unsafe {
            let node_ref = &*node.as_ptr();
            self.next = node_ref.next;
            Some(&node_ref.data)
        }
    }
}

impl<T> Drop for LinkedList<T> {
    fn drop(&mut self) {
        let mut current = self.front;
        while let Some(node) = current {
            // SAFETY: each node is owned by this list and was allocated by
            // `boxed_node` (invariant (1)). We read `next` before reclaiming the
            // node, and never touch the node again afterwards.
            unsafe {
                let next = (*node.as_ptr()).next;
                drop(Box::from_raw(node.as_ptr()));
                current = next;
            }
        }
        self.front = None;
        self.back = None;
        self.len = 0;
    }
}

// SAFETY: `LinkedList<T>` uniquely owns its heap-allocated nodes, and the only
// safe ways to reach them are `&self` (through `iter`) and `&mut self` (through
// the cursors). Sending the list to another thread therefore moves the sole
// ownership of all `T`s, which is sound when `T: Send`.
unsafe impl<T: Send> Send for LinkedList<T> {}

// SAFETY: `&LinkedList<T>` only allows obtaining `&T` (via `iter`, which cannot
// mutate or free nodes), so sharing the list between threads is exactly sharing
// `&T`, which is sound when `T: Sync`.
unsafe impl<T: Sync> Sync for LinkedList<T> {}

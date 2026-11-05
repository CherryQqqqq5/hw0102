// this module adds some functionality based on the required implementations
// here like: `LinkedList::pop_back` or `Clone for LinkedList<T>`
// You are free to use anything in it, but it's mainly for the test framework.
mod pre_implemented;

use std::marker::PhantomData;
use std::ptr::NonNull;

/// A single node of the doubly linked list.
///
/// # Safety invariants
///
/// All of the following must hold for every `LinkedList<T>` that exists:
///
/// * Every `NonNull` stored in a node's `next`/`prev` points to a live
///   `Node<T>` allocated by (and owned by) the same list.
/// * Links are symmetric: if `n.next == Some(m)` then `m.prev == Some(n)`, and
///   if `n.prev == Some(p)` then `p.next == Some(n)`.
/// * `list.head` is the unique node with `prev == None`, `list.tail` is the
///   unique node with `next == None`. Both are `None` iff the list is empty.
/// * `list.len` is exactly the number of reachable nodes.
/// * Each node is reachable from exactly one place (the list or nobody), so it
///   is freed exactly once.
struct Node<T> {
    data: T,
    next: Option<NonNull<Node<T>>>,
    prev: Option<NonNull<Node<T>>>,
}

pub struct LinkedList<T> {
    head: Option<NonNull<Node<T>>>,
    tail: Option<NonNull<Node<T>>>,
    len: usize,
    /// `PhantomData<Box<Node<T>>>` makes `LinkedList<T>` *covariant* over `T`
    /// and tells dropck that the list owns its `T`s.
    _marker: PhantomData<Box<Node<T>>>,
}

pub struct Cursor<'a, T> {
    /// The node the cursor sits on. `None` when the list is empty (or the
    /// cursor has been moved past one of the ends of the list).
    current: Option<NonNull<Node<T>>>,
    /// The exclusively borrowed list. Holding `&'a mut LinkedList<T>` guarantees
    /// no other code can observe the list while the cursor is alive.
    list: &'a mut LinkedList<T>,
}

pub struct Iter<'a, T> {
    next: Option<NonNull<Node<T>>>,
    /// Covariant over both `'a` and `T`.
    _marker: PhantomData<&'a T>,
}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        LinkedList {
            head: None,
            tail: None,
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
        let current = self.head;
        Cursor { current, list: self }
    }

    /// Return a cursor positioned on the back element
    pub fn cursor_back(&mut self) -> Cursor<'_, T> {
        let current = self.tail;
        Cursor { current, list: self }
    }

    /// Return an iterator that moves from front to back
    pub fn iter(&self) -> Iter<'_, T> {
        Iter {
            next: self.head,
            _marker: PhantomData,
        }
    }
}

impl<T> Default for LinkedList<T> {
    fn default() -> Self {
        Self::new()
    }
}

// The cursor is expected to act as if it is at the position of an element
// and it also has to work with and be able to insert into an empty list.
impl<'a, T> Cursor<'a, T> {
    /// Take a mutable reference to the current element
    pub fn peek_mut(&mut self) -> Option<&mut T> {
        // SAFETY: `self.current` is either `None` or a live node owned by
        // `self.list` (guaranteed by the list invariants). The exclusive borrow
        // of the list held by the cursor means this `&mut` is unique.
        self.current
            .map(|node| unsafe { &mut (*node.as_ptr()).data })
    }

    /// Move one position forward (towards the back) and
    /// return a reference to the new position
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&mut T> {
        if let Some(node) = self.current {
            // SAFETY: `node` is a live node owned by the list, so its `next`
            // field is either `None` or another live node of the same list.
            self.current = unsafe { (*node.as_ptr()).next };
        }
        self.peek_mut()
    }

    /// Move one position backward (towards the front) and
    /// return a reference to the new position
    pub fn prev(&mut self) -> Option<&mut T> {
        if let Some(node) = self.current {
            // SAFETY: same reasoning as in `next`.
            self.current = unsafe { (*node.as_ptr()).prev };
        }
        self.peek_mut()
    }

    /// Remove and return the element at the current position and move the cursor
    /// to the neighboring element that's closest to the back. This can be
    /// either the next or previous position.
    pub fn take(&mut self) -> Option<T> {
        let node = self.current?;

        // SAFETY: `node` is a live node of the list, therefore its `prev`/`next`
        // are `None` or live nodes of the same list, and `len >= 1`.
        unsafe {
            let next = (*node.as_ptr()).next;
            let prev = (*node.as_ptr()).prev;

            // Unlink the node from its neighbours (or from the list ends).
            match prev {
                Some(prev) => (*prev.as_ptr()).next = next,
                None => self.list.head = next,
            }
            match next {
                Some(next) => (*next.as_ptr()).prev = prev,
                None => self.list.tail = prev,
            }
            self.list.len -= 1;

            // Move to the neighbouring element closest to the back.
            self.current = next.or(prev);

            // SAFETY: the node is now unreachable from the list and nothing else
            // owns it, so we may take ownership of the allocation. It is dropped
            // exactly once, here.
            let node = Box::from_raw(node.as_ptr());
            let Node { data, .. } = *node;
            Some(data)
        }
    }

    pub fn insert_after(&mut self, element: T) {
        // SAFETY: `Box::into_raw` gives us ownership of a fresh, valid node; it is
        // linked into the list below so nothing leaks.
        let new = NonNull::from(unsafe {
            &mut *Box::into_raw(Box::new(Node {
                data: element,
                next: None,
                prev: None,
            }))
        });

        unsafe {
            match self.current {
                Some(current) => {
                    // SAFETY: `current` is a live node of the list.
                    let next = (*current.as_ptr()).next;

                    (*new.as_ptr()).prev = Some(current);
                    (*new.as_ptr()).next = next;
                    (*current.as_ptr()).next = Some(new);

                    match next {
                        Some(next) => (*next.as_ptr()).prev = Some(new),
                        None => self.list.tail = Some(new),
                    }
                }
                None => {
                    // The cursor is not on a node, so either the list is empty or
                    // the cursor sits past the back: append at the back.
                    let tail = self.list.tail;
                    (*new.as_ptr()).prev = tail;
                    match tail {
                        Some(tail) => (*tail.as_ptr()).next = Some(new),
                        None => self.list.head = Some(new),
                    }
                    self.list.tail = Some(new);
                }
            }
        }

        self.list.len += 1;
    }

    pub fn insert_before(&mut self, element: T) {
        // SAFETY: as in `insert_after`, we own the freshly allocated node and
        // immediately link it into the list.
        let new = NonNull::from(unsafe {
            &mut *Box::into_raw(Box::new(Node {
                data: element,
                next: None,
                prev: None,
            }))
        });

        unsafe {
            match self.current {
                Some(current) => {
                    // SAFETY: `current` is a live node of the list.
                    let prev = (*current.as_ptr()).prev;

                    (*new.as_ptr()).next = Some(current);
                    (*new.as_ptr()).prev = prev;
                    (*current.as_ptr()).prev = Some(new);

                    match prev {
                        Some(prev) => (*prev.as_ptr()).next = Some(new),
                        None => self.list.head = Some(new),
                    }
                }
                None => {
                    // The cursor is not on a node, so either the list is empty or
                    // the cursor sits in front of the front: insert at the front.
                    let head = self.list.head;
                    (*new.as_ptr()).next = head;
                    match head {
                        Some(head) => (*head.as_ptr()).prev = Some(new),
                        None => self.list.tail = Some(new),
                    }
                    self.list.head = Some(new);
                }
            }
        }

        self.list.len += 1;
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<&'a T> {
        let node = self.next?;
        // SAFETY: `node` is a live node of a list that is borrowed for `'a`, so
        // the returned reference cannot outlive the list. The iterator only ever
        // hands out shared references, so aliasing is fine.
        unsafe {
            self.next = (*node.as_ptr()).next;
            Some(&(*node.as_ptr()).data)
        }
    }
}

impl<T> Drop for LinkedList<T> {
    fn drop(&mut self) {
        let mut current = self.head;
        while let Some(node) = current {
            // SAFETY: each node is reachable from exactly one place, so walking
            // the chain from the front frees every allocation exactly once. We
            // read `next` before freeing the node.
            unsafe {
                let next = (*node.as_ptr()).next;
                drop(Box::from_raw(node.as_ptr()));
                current = next;
            }
        }
        self.head = None;
        self.tail = None;
    }
}

// SAFETY: `LinkedList<T>` owns its nodes and hands out `&mut T`/`&T` only via
// regular borrows, so sending the list to another thread is safe whenever `T`
// may be sent, and sharing it is safe whenever `T` may be shared.
unsafe impl<T: Send> Send for LinkedList<T> {}
unsafe impl<T: Sync> Sync for LinkedList<T> {}

// SAFETY: `Iter` is just a shared borrow of the list, so the same bounds apply.
unsafe impl<'a, T: Sync> Send for Iter<'a, T> {}
unsafe impl<'a, T: Sync> Sync for Iter<'a, T> {}

//! A doubly linked list written with `unsafe` Rust.
//!
//! # Safety invariants
//!
//! Every `unsafe` block in this file relies on the following invariants, which
//! all the functions below uphold:
//!
//! 1. Every `NonNull<Node<T>>` stored in the list (`head`, `tail`, `next`,
//!    `prev`, or held by a `Cursor`) points to a live, aligned, initialised
//!    `Node<T>` that was created with `Box::into_raw` and is *owned* by the
//!    list.
//! 2. `head.is_none() == tail.is_none() == (len == 0)`. `head`'s `prev` is
//!    `None`, `tail`'s `next` is `None`, and for every node `n` that has a
//!    successor `s`, `s.prev == n`, and vice versa.
//! 3. `len` is exactly the number of nodes reachable from `head` through `next`.
//! 4. Each node is reachable exactly once, so it is freed exactly once: either
//!    in `Cursor::take` or in `Drop`.
//! 5. No `&mut` alias is created while another reference to the same element is
//!    alive. This is enforced by the borrow checker: all mutating access goes
//!    through a `Cursor<'a, T>`, which holds `&'a mut LinkedList<T>`, and the
//!    references it hands out are tied to `&mut self`.

use std::marker::PhantomData;
use std::ptr::NonNull;

// this module adds some functionality based on the required implementations
// here like: `LinkedList::pop_back` or `Clone for LinkedList<T>`
// You are free to use anything in it, but it's mainly for the test framework.
mod pre_implemented;

/// A single list node. Owned by the list through a raw pointer.
struct Node<T> {
    element: T,
    next: Option<NonNull<Node<T>>>,
    prev: Option<NonNull<Node<T>>>,
}

/// A doubly linked list.
///
/// All pointers to `T` live behind `NonNull`, which is covariant over its
/// pointee, so `LinkedList<T>` is covariant over `T`. `Send`/`Sync` are
/// implemented manually below because raw pointers are neither.
pub struct LinkedList<T> {
    head: Option<NonNull<Node<T>>>,
    tail: Option<NonNull<Node<T>>>,
    len: usize,
}

/// A cursor onto a position inside a `LinkedList`.
///
/// `cur` is `None` only for an empty list or when the cursor has been moved
/// past either end of the list.
pub struct Cursor<'a, T> {
    list: &'a mut LinkedList<T>,
    cur: Option<NonNull<Node<T>>>,
}

/// An iterator over `&T`, from front to back.
pub struct Iter<'a, T> {
    front: Option<NonNull<Node<T>>>,
    back: Option<NonNull<Node<T>>>,
    len: usize,
    marker: PhantomData<&'a T>,
}

impl<T> LinkedList<T> {
    pub fn new() -> Self {
        Self {
            head: None,
            tail: None,
            len: 0,
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
        let cur = self.head;
        Cursor { list: self, cur }
    }

    /// Return a cursor positioned on the back element
    pub fn cursor_back(&mut self) -> Cursor<'_, T> {
        let cur = self.tail;
        Cursor { list: self, cur }
    }

    /// Return an iterator that moves from front to back
    pub fn iter(&self) -> Iter<'_, T> {
        Iter {
            front: self.head,
            back: self.tail,
            len: self.len,
            marker: PhantomData,
        }
    }
}

// the cursor is expected to act as if it is at the position of an element
// and it also has to work with and be able to insert into an empty list.
impl<T> Cursor<'_, T> {
    /// Take a mutable reference to the current element
    pub fn peek_mut(&mut self) -> Option<&mut T> {
        let cur = self.cur?;
        // SAFETY: invariant 1 -- `cur` points at a live node owned by `self.list`,
        // and no other reference to its element exists (invariant 5). The returned
        // reference is tied to `&mut self`.
        unsafe { Some(&mut (*cur.as_ptr()).element) }
    }

    /// Move one position forward (towards the back) and
    /// return a reference to the new position
    #[allow(clippy::should_implement_trait)]
    pub fn next(&mut self) -> Option<&mut T> {
        let cur = self.cur?;
        // SAFETY: invariant 1 -- `cur` points at a live node; its `next` field is
        // either `None` or another live node owned by the list (invariants 1, 2).
        self.cur = unsafe { (*cur.as_ptr()).next };
        self.peek_mut()
    }

    /// Move one position backward (towards the front) and
    /// return a reference to the new position
    pub fn prev(&mut self) -> Option<&mut T> {
        let cur = self.cur?;
        // SAFETY: invariant 1 -- `cur` points at a live node; its `prev` field is
        // either `None` or another live node owned by the list (invariants 1, 2).
        self.cur = unsafe { (*cur.as_ptr()).prev };
        self.peek_mut()
    }

    /// Remove and return the element at the current position and move the cursor
    /// to the neighboring element that's closest to the back. This can be
    /// either the next or previous position.
    pub fn take(&mut self) -> Option<T> {
        let cur = self.cur?;
        // SAFETY: invariant 1 -- `cur` points at a live node that is owned by
        // `self.list`. We take ownership of it here and never touch it again
        // after `Box::from_raw`, so it is freed exactly once (invariant 4). The
        // neighbours are updated so that invariants 2 and 3 hold again.
        unsafe {
            let node = cur.as_ptr();
            let prev = (*node).prev;
            let next = (*node).next;

            match prev {
                Some(prev) => (*prev.as_ptr()).next = next,
                None => self.list.head = next,
            }
            match next {
                Some(next) => (*next.as_ptr()).prev = prev,
                None => self.list.tail = prev,
            }

            self.list.len -= 1;
            // The neighbour closest to the back is the successor if there is one.
            self.cur = next.or(prev);

            // Reclaim ownership of the node; moving the element out of the box is
            // allowed and the (now empty) allocation is freed at the end here.
            Some(Box::from_raw(node).element)
        }
    }

    pub fn insert_after(&mut self, element: T) {
        // SAFETY: `Box::into_raw` gives a uniquely owned, live node pointer which
        // has not been handed out anywhere else yet.
        let new_node = unsafe {
            NonNull::new_unchecked(Box::into_raw(Box::new(Node {
                element,
                next: None,
                prev: None,
            })))
        };

        match self.cur {
            Some(cur) => {
                // SAFETY: both `cur` and `new_node` are live, distinct nodes; `cur`
                // is owned by the list, `new_node` by us. All links are updated
                // consistently (invariant 2).
                unsafe {
                    let next = (*cur.as_ptr()).next;
                    (*new_node.as_ptr()).next = next;
                    (*new_node.as_ptr()).prev = Some(cur);
                    (*cur.as_ptr()).next = Some(new_node);
                    match next {
                        Some(next) => (*next.as_ptr()).prev = Some(new_node),
                        None => self.list.tail = Some(new_node),
                    }
                }
            }
            None => {
                // Empty list, or the cursor walked off the back: append at the back.
                let tail = self.list.tail;
                // SAFETY: `new_node` is live and unlinked; `tail` is either `None`
                // or the live last node of the list (invariant 1, 2).
                unsafe {
                    (*new_node.as_ptr()).prev = tail;
                    match tail {
                        Some(tail) => (*tail.as_ptr()).next = Some(new_node),
                        None => self.list.head = Some(new_node),
                    }
                }
                self.list.tail = Some(new_node);
                self.cur = Some(new_node);
            }
        }

        self.list.len += 1;
    }

    pub fn insert_before(&mut self, element: T) {
        // SAFETY: `Box::into_raw` gives a uniquely owned, live node pointer which
        // has not been handed out anywhere else yet.
        let new_node = unsafe {
            NonNull::new_unchecked(Box::into_raw(Box::new(Node {
                element,
                next: None,
                prev: None,
            })))
        };

        match self.cur {
            Some(cur) => {
                // SAFETY: both `cur` and `new_node` are live, distinct nodes; `cur`
                // is owned by the list, `new_node` by us. All links are updated
                // consistently (invariant 2).
                unsafe {
                    let prev = (*cur.as_ptr()).prev;
                    (*new_node.as_ptr()).next = Some(cur);
                    (*new_node.as_ptr()).prev = prev;
                    (*cur.as_ptr()).prev = Some(new_node);
                    match prev {
                        Some(prev) => (*prev.as_ptr()).next = Some(new_node),
                        None => self.list.head = Some(new_node),
                    }
                }
            }
            None => {
                // Empty list, or the cursor walked off an end: append at the back.
                let tail = self.list.tail;
                // SAFETY: `new_node` is live and unlinked; `tail` is either `None`
                // or the live last node of the list (invariant 1, 2).
                unsafe {
                    (*new_node.as_ptr()).prev = tail;
                    match tail {
                        Some(tail) => (*tail.as_ptr()).next = Some(new_node),
                        None => self.list.head = Some(new_node),
                    }
                }
                self.list.tail = Some(new_node);
                self.cur = Some(new_node);
            }
        }

        self.list.len += 1;
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<&'a T> {
        if self.len == 0 {
            return None;
        }
        let front = self.front?;
        self.len -= 1;
        // SAFETY: `front` points at a live node owned by the borrowed list. The
        // shared reference we produce lives at most as long as `'a`, and the list
        // is borrowed immutably for `'a`, so no `&mut` to it can exist meanwhile.
        unsafe {
            let node = &*front.as_ptr();
            self.front = node.next;
            Some(&node.element)
        }
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.len, Some(self.len))
    }
}

impl<'a, T> DoubleEndedIterator for Iter<'a, T> {
    fn next_back(&mut self) -> Option<&'a T> {
        if self.len == 0 {
            return None;
        }
        let back = self.back?;
        self.len -= 1;
        // SAFETY: `back` points at a live node owned by the borrowed list; same
        // reasoning as in `next`.
        unsafe {
            let node = &*back.as_ptr();
            self.back = node.prev;
            Some(&node.element)
        }
    }
}

impl<T> Drop for LinkedList<T> {
    fn drop(&mut self) {
        let mut cur = self.head;
        while let Some(node) = cur {
            // SAFETY: every node is reachable exactly once from `head`, so this
            // loop visits and frees each of them exactly once. `next` is read
            // before the node is deallocated.
            unsafe {
                cur = (*node.as_ptr()).next;
                drop(Box::from_raw(node.as_ptr()));
            }
        }
    }
}

// SAFETY: a `LinkedList<T>` owns all of its nodes and hands out references with
// the same aliasing discipline as `Box<T>`, therefore it can be transferred to
// another thread whenever `T` can, and shared whenever `T` can be shared.
unsafe impl<T: Send> Send for LinkedList<T> {}
unsafe impl<T: Sync> Sync for LinkedList<T> {}

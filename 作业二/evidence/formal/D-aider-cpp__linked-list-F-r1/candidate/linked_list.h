#pragma once

#include <cstddef>
#include <stdexcept>

namespace linked_list {

template <typename T>
class List {
private:
    struct Node {
        T value;
        Node* prev;
        Node* next;

        explicit Node(const T& v) : value{v}, prev{nullptr}, next{nullptr} {}
    };

    Node* head_{nullptr};
    Node* tail_{nullptr};
    std::size_t size_{0};

    void clear() {
        Node* current = head_;
        while (current != nullptr) {
            Node* next = current->next;
            delete current;
            current = next;
        }
        head_ = nullptr;
        tail_ = nullptr;
        size_ = 0;
    }

public:
    List() = default;

    List(const List&) = delete;
    List& operator=(const List&) = delete;

    ~List() { clear(); }

    // Adds an element to the end of the list.
    void push(const T& value) {
        Node* node = new Node(value);
        node->prev = tail_;
        if (tail_ != nullptr) {
            tail_->next = node;
        } else {
            head_ = node;
        }
        tail_ = node;
        ++size_;
    }

    // Removes and returns the last element of the list.
    T pop() {
        if (tail_ == nullptr) {
            throw std::out_of_range("pop from empty list");
        }
        Node* node = tail_;
        T value = node->value;
        tail_ = node->prev;
        if (tail_ != nullptr) {
            tail_->next = nullptr;
        } else {
            head_ = nullptr;
        }
        delete node;
        --size_;
        return value;
    }

    // Removes and returns the first element of the list.
    T shift() {
        if (head_ == nullptr) {
            throw std::out_of_range("shift from empty list");
        }
        Node* node = head_;
        T value = node->value;
        head_ = node->next;
        if (head_ != nullptr) {
            head_->prev = nullptr;
        } else {
            tail_ = nullptr;
        }
        delete node;
        --size_;
        return value;
    }

    // Adds an element to the start of the list.
    void unshift(const T& value) {
        Node* node = new Node(value);
        node->next = head_;
        if (head_ != nullptr) {
            head_->prev = node;
        } else {
            tail_ = node;
        }
        head_ = node;
        ++size_;
    }

    // Returns the total number of elements in the current list.
    std::size_t count() const { return size_; }

    // Removes the first occurrence of value; returns whether one was removed.
    bool erase(const T& value) {
        for (Node* node = head_; node != nullptr; node = node->next) {
            if (node->value == value) {
                if (node->prev != nullptr) {
                    node->prev->next = node->next;
                } else {
                    head_ = node->next;
                }
                if (node->next != nullptr) {
                    node->next->prev = node->prev;
                } else {
                    tail_ = node->prev;
                }
                delete node;
                --size_;
                return true;
            }
        }
        return false;
    }
};

}  // namespace linked_list

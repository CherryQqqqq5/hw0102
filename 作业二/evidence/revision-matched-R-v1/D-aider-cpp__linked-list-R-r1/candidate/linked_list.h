#pragma once

#include <cstddef>
#include <stdexcept>
#include <utility>

namespace linked_list {

template <typename T>
class List {
private:
    struct Node {
        T value;
        Node* prev;
        Node* next;

        explicit Node(const T& v) : value(v), prev(nullptr), next(nullptr) {}
        explicit Node(T&& v) : value(std::move(v)), prev(nullptr), next(nullptr) {}
    };

    Node* head_{nullptr};
    Node* tail_{nullptr};
    std::size_t count_{0};

    void remove_node(Node* node) noexcept {
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
        --count_;
    }

public:
    List() noexcept = default;

    ~List() {
        clear();
    }

    List(const List& other) {
        for (Node* node = other.head_; node != nullptr; node = node->next) {
            push(node->value);
        }
    }

    List(List&& other) noexcept
        : head_(other.head_), tail_(other.tail_), count_(other.count_) {
        other.head_ = nullptr;
        other.tail_ = nullptr;
        other.count_ = 0;
    }

    List& operator=(List other) {
        swap(other);
        return *this;
    }

    void swap(List& other) noexcept {
        std::swap(head_, other.head_);
        std::swap(tail_, other.tail_);
        std::swap(count_, other.count_);
    }

    void push(const T& value) {
        Node* node = new Node(value);
        if (tail_ == nullptr) {
            head_ = tail_ = node;
        } else {
            node->prev = tail_;
            tail_->next = node;
            tail_ = node;
        }
        ++count_;
    }

    void push(T&& value) {
        Node* node = new Node(std::move(value));
        if (tail_ == nullptr) {
            head_ = tail_ = node;
        } else {
            node->prev = tail_;
            tail_->next = node;
            tail_ = node;
        }
        ++count_;
    }

    T pop() {
        if (tail_ == nullptr) {
            throw std::out_of_range("pop from empty list");
        }
        Node* node = tail_;
        T value = std::move(node->value);
        remove_node(node);
        return value;
    }

    T shift() {
        if (head_ == nullptr) {
            throw std::out_of_range("shift from empty list");
        }
        Node* node = head_;
        T value = std::move(node->value);
        remove_node(node);
        return value;
    }

    void unshift(const T& value) {
        Node* node = new Node(value);
        if (head_ == nullptr) {
            head_ = tail_ = node;
        } else {
            node->next = head_;
            head_->prev = node;
            head_ = node;
        }
        ++count_;
    }

    void unshift(T&& value) {
        Node* node = new Node(std::move(value));
        if (head_ == nullptr) {
            head_ = tail_ = node;
        } else {
            node->next = head_;
            head_->prev = node;
            head_ = node;
        }
        ++count_;
    }

    std::size_t count() const noexcept {
        return count_;
    }

    bool erase(const T& value) {
        Node* node = head_;
        while (node != nullptr && !(node->value == value)) {
            node = node->next;
        }

        if (node == nullptr) {
            return false;
        }

        remove_node(node);
        return true;
    }

    void clear() noexcept {
        Node* node = head_;
        while (node != nullptr) {
            Node* next = node->next;
            delete node;
            node = next;
        }
        head_ = nullptr;
        tail_ = nullptr;
        count_ = 0;
    }
};

}  // namespace linked_list

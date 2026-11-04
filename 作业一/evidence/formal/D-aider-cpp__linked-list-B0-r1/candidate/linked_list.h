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

    void swap(List& other) noexcept {
        std::swap(head_, other.head_);
        std::swap(tail_, other.tail_);
        std::swap(size_, other.size_);
    }

   public:
    List() = default;

    List(const List& other) {
        for (Node* current = other.head_; current != nullptr; current = current->next) {
            push(current->value);
        }
    }

    List(List&& other) noexcept
        : head_(other.head_), tail_(other.tail_), size_(other.size_) {
        other.head_ = nullptr;
        other.tail_ = nullptr;
        other.size_ = 0;
    }

    List& operator=(const List& other) {
        if (this != &other) {
            List copy(other);
            swap(copy);
        }
        return *this;
    }

    List& operator=(List&& other) noexcept {
        if (this != &other) {
            clear();
            head_ = other.head_;
            tail_ = other.tail_;
            size_ = other.size_;
            other.head_ = nullptr;
            other.tail_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }

    ~List() { clear(); }

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

    void push(T&& value) {
        Node* node = new Node(std::move(value));
        node->prev = tail_;
        if (tail_ != nullptr) {
            tail_->next = node;
        } else {
            head_ = node;
        }
        tail_ = node;
        ++size_;
    }

    T pop() {
        if (tail_ == nullptr) {
            throw std::runtime_error("pop from empty list");
        }
        Node* node = tail_;
        T value = std::move(node->value);
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

    T shift() {
        if (head_ == nullptr) {
            throw std::runtime_error("shift from empty list");
        }
        Node* node = head_;
        T value = std::move(node->value);
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

    void unshift(T&& value) {
        Node* node = new Node(std::move(value));
        node->next = head_;
        if (head_ != nullptr) {
            head_->prev = node;
        } else {
            tail_ = node;
        }
        head_ = node;
        ++size_;
    }

    std::size_t count() const noexcept { return size_; }

    bool erase(const T& value) {
        for (Node* current = head_; current != nullptr; current = current->next) {
            if (current->value == value) {
                if (current->prev != nullptr) {
                    current->prev->next = current->next;
                } else {
                    head_ = current->next;
                }
                if (current->next != nullptr) {
                    current->next->prev = current->prev;
                } else {
                    tail_ = current->prev;
                }
                delete current;
                --size_;
                return true;
            }
        }
        return false;
    }
};

}  // namespace linked_list

#pragma once

#include <cstddef>
#include <utility>

namespace linked_list {

template <typename T>
class List {
   public:
    List() = default;

    List(const List& other) {
        for (Node* cur = other.head_; cur != nullptr; cur = cur->next) {
            push(cur->value);
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
            clear();
            for (Node* cur = other.head_; cur != nullptr; cur = cur->next) {
                push(cur->value);
            }
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
        Node* node = new Node{value, nullptr, nullptr};
        if (tail_ == nullptr) {
            head_ = node;
            tail_ = node;
        } else {
            node->prev = tail_;
            tail_->next = node;
            tail_ = node;
        }
        ++size_;
    }

    T pop() {
        Node* node = tail_;
        T value = node->value;
        tail_ = node->prev;
        if (tail_ == nullptr) {
            head_ = nullptr;
        } else {
            tail_->next = nullptr;
        }
        delete node;
        --size_;
        return value;
    }

    T shift() {
        Node* node = head_;
        T value = node->value;
        head_ = node->next;
        if (head_ == nullptr) {
            tail_ = nullptr;
        } else {
            head_->prev = nullptr;
        }
        delete node;
        --size_;
        return value;
    }

    void unshift(const T& value) {
        Node* node = new Node{value, nullptr, nullptr};
        if (head_ == nullptr) {
            head_ = node;
            tail_ = node;
        } else {
            node->next = head_;
            head_->prev = node;
            head_ = node;
        }
        ++size_;
    }

    std::size_t count() const { return size_; }

    bool erase(const T& value) {
        for (Node* cur = head_; cur != nullptr; cur = cur->next) {
            if (cur->value == value) {
                if (cur->prev == nullptr) {
                    head_ = cur->next;
                } else {
                    cur->prev->next = cur->next;
                }
                if (cur->next == nullptr) {
                    tail_ = cur->prev;
                } else {
                    cur->next->prev = cur->prev;
                }
                delete cur;
                --size_;
                return true;
            }
        }
        return false;
    }

   private:
    struct Node {
        T value;
        Node* prev;
        Node* next;
    };

    Node* head_ = nullptr;
    Node* tail_ = nullptr;
    std::size_t size_ = 0;

    void clear() {
        Node* cur = head_;
        while (cur != nullptr) {
            Node* next = cur->next;
            delete cur;
            cur = next;
        }
        head_ = nullptr;
        tail_ = nullptr;
        size_ = 0;
    }
};

}  // namespace linked_list

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

    void push(const T& value) {
        Node* node = new Node{value};
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
            throw std::runtime_error("pop called on an empty list");
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

    T shift() {
        if (head_ == nullptr) {
            throw std::runtime_error("shift called on an empty list");
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

    void unshift(const T& value) {
        Node* node = new Node{value};
        node->next = head_;
        if (head_ != nullptr) {
            head_->prev = node;
        } else {
            tail_ = node;
        }
        head_ = node;
        ++size_;
    }

    std::size_t count() const { return size_; }

    bool erase(const T& value) {
        Node* current = head_;
        while (current != nullptr) {
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
            current = current->next;
        }
        return false;
    }
};

}  // namespace linked_list

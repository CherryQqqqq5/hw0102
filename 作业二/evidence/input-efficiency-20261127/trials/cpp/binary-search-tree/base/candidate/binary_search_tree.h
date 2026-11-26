#if !defined(BINARY_SEARCH_TREE_H)
#define BINARY_SEARCH_TREE_H

#include <cstddef>
#include <iterator>
#include <memory>
#include <string>
#include <type_traits>
#include <vector>

namespace binary_search_tree {

template <typename T>
class binary_tree {
public:
    explicit binary_tree(const T& value) : data_(value) {}

    const T& data() const { return data_; }

    const std::unique_ptr<binary_tree<T>>& left() const { return left_; }
    const std::unique_ptr<binary_tree<T>>& right() const { return right_; }

    void insert(const T& value)
    {
        if (value < data_) {
            if (left_) {
                left_->insert(value);
            } else {
                left_.reset(new binary_tree<T>(value));
            }
        } else if (data_ < value) {
            if (right_) {
                right_->insert(value);
            } else {
                right_.reset(new binary_tree<T>(value));
            }
        } else {
            // Values equal to the current node belong in the left subtree.
            if (left_) {
                left_->insert(value);
            } else {
                left_.reset(new binary_tree<T>(value));
            }
        }
    }

    template <bool IsConst>
    class basic_iterator {
    public:
        using iterator_category = std::forward_iterator_tag;
        using value_type = T;
        using difference_type = std::ptrdiff_t;
        using node_type = typename std::conditional<IsConst, const binary_tree<T>, binary_tree<T>>::type;
        using pointer = typename std::conditional<IsConst, const T*, T*>::type;
        using reference = typename std::conditional<IsConst, const T&, T&>::type;

        basic_iterator() = default;

        reference operator*() const { return stack_.back()->data_; }
        pointer operator->() const { return &(stack_.back()->data_); }

        basic_iterator& operator++()
        {
            node_type* node = stack_.back();
            stack_.pop_back();
            push_left(node->right_.get());
            return *this;
        }

        basic_iterator operator++(int)
        {
            basic_iterator old(*this);
            ++(*this);
            return old;
        }

        bool operator==(const basic_iterator& other) const
        {
            return stack_ == other.stack_;
        }

        bool operator!=(const basic_iterator& other) const
        {
            return !(*this == other);
        }

    private:
        friend class binary_tree<T>;

        explicit basic_iterator(node_type* node)
        {
            push_left(node);
        }

        void push_left(node_type* node)
        {
            while (node != nullptr) {
                stack_.push_back(node);
                node = node->left_.get();
            }
        }

        std::vector<node_type*> stack_;
    };

    using iterator = basic_iterator<false>;
    using const_iterator = basic_iterator<true>;

    iterator begin() { return iterator(this); }
    iterator end() { return iterator(); }

    const_iterator begin() const { return const_iterator(this); }
    const_iterator end() const { return const_iterator(); }
    const_iterator cbegin() const { return begin(); }
    const_iterator cend() const { return end(); }

private:
    T data_;
    std::unique_ptr<binary_tree<T>> left_;
    std::unique_ptr<binary_tree<T>> right_;
};

}  // namespace binary_search_tree

#endif // BINARY_SEARCH_TREE_H

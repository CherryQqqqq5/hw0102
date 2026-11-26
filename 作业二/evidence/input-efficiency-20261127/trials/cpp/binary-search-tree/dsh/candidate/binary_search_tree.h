#if !defined(BINARY_SEARCH_TREE_H)
#define BINARY_SEARCH_TREE_H

#include <cstddef>
#include <iterator>
#include <memory>
#include <type_traits>
#include <vector>

namespace binary_search_tree {

template <typename T>
class binary_tree {
public:
    using value_type = T;

    explicit binary_tree(const T& value) : data_(value)
    {
    }

    void insert(const T& value)
    {
        if (data_ < value) {
            if (right_) {
                right_->insert(value);
            } else {
                right_.reset(new binary_tree(value));
            }
        } else {
            if (left_) {
                left_->insert(value);
            } else {
                left_.reset(new binary_tree(value));
            }
        }
    }

    const T& data() const
    {
        return data_;
    }

    const std::unique_ptr<binary_tree<T>>& left() const
    {
        return left_;
    }

    const std::unique_ptr<binary_tree<T>>& right() const
    {
        return right_;
    }

    template <bool IsConst>
    class basic_iterator {
    public:
        using node_type =
            typename std::conditional<IsConst, const binary_tree<T>, binary_tree<T>>::type;
        using iterator_category = std::forward_iterator_tag;
        using value_type = T;
        using difference_type = std::ptrdiff_t;
        using pointer = typename std::conditional<IsConst, const T*, T*>::type;
        using reference = typename std::conditional<IsConst, const T&, T&>::type;

        basic_iterator() = default;

        reference operator*() const
        {
            return nodes_.back()->data_;
        }

        pointer operator->() const
        {
            return &(**this);
        }

        basic_iterator& operator++()
        {
            if (nodes_.empty()) {
                return *this;
            }

            node_type* current = nodes_.back();
            nodes_.pop_back();

            if (current->right_) {
                push_left(current->right_.get());
            }

            return *this;
        }

        basic_iterator operator++(int)
        {
            basic_iterator copy(*this);
            ++(*this);
            return copy;
        }

        friend bool operator==(const basic_iterator& lhs, const basic_iterator& rhs)
        {
            return lhs.nodes_ == rhs.nodes_;
        }

        friend bool operator!=(const basic_iterator& lhs, const basic_iterator& rhs)
        {
            return !(lhs == rhs);
        }

    private:
        friend class binary_tree<T>;
        template <bool> friend class basic_iterator;

        std::vector<node_type*> nodes_;

        explicit basic_iterator(node_type* root)
        {
            push_left(root);
        }

        void push_left(node_type* node)
        {
            while (node != nullptr) {
                nodes_.push_back(node);
                node = node->left_.get();
            }
        }
    };

    using iterator = basic_iterator<false>;
    using const_iterator = basic_iterator<true>;

    iterator begin()
    {
        return iterator(this);
    }

    iterator end()
    {
        return iterator();
    }

    const_iterator begin() const
    {
        return const_iterator(this);
    }

    const_iterator end() const
    {
        return const_iterator();
    }

    const_iterator cbegin() const
    {
        return begin();
    }

    const_iterator cend() const
    {
        return end();
    }

private:
    T data_;
    std::unique_ptr<binary_tree<T>> left_;
    std::unique_ptr<binary_tree<T>> right_;
};

}  // namespace binary_search_tree

#endif // BINARY_SEARCH_TREE_H

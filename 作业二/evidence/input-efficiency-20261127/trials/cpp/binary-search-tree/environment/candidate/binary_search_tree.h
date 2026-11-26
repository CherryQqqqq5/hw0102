#if !defined(BINARY_SEARCH_TREE_H)
#define BINARY_SEARCH_TREE_H

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace binary_search_tree {

template <typename T>
class binary_tree {
public:
    template <typename NodePointer, typename Reference, typename Pointer>
    class basic_iterator {
    public:
        using iterator_category = std::bidirectional_iterator_tag;
        using value_type = T;
        using difference_type = std::ptrdiff_t;
        using reference = Reference;
        using pointer = Pointer;

        basic_iterator() = default;

        basic_iterator(NodePointer root, bool from_begin)
            : root_(root)
        {
            if (from_begin) {
                descend_left(root_);
            }
        }

        reference operator*() const
        {
            return path_.back()->data_;
        }

        pointer operator->() const
        {
            return &(path_.back()->data_);
        }

        basic_iterator& operator++()
        {
            NodePointer node = path_.back();
            if (node->right_) {
                descend_left(node->right_.get());
            } else {
                ascend_to_left_parent();
            }
            return *this;
        }

        basic_iterator operator++(int)
        {
            basic_iterator copy(*this);
            ++(*this);
            return copy;
        }

        basic_iterator& operator--()
        {
            if (path_.empty()) {
                descend_right(root_);
            } else {
                NodePointer node = path_.back();
                if (node->left_) {
                    descend_right(node->left_.get());
                } else {
                    ascend_to_right_parent();
                }
            }
            return *this;
        }

        basic_iterator operator--(int)
        {
            basic_iterator copy(*this);
            --(*this);
            return copy;
        }

        template <typename OtherNodePointer, typename OtherReference, typename OtherPointer>
        bool operator==(const basic_iterator<OtherNodePointer, OtherReference, OtherPointer>& other) const
        {
            if (root_ != other.root_node() || path_.size() != other.traversal_path().size()) {
                return false;
            }
            for (std::size_t i = 0; i < path_.size(); ++i) {
                if (path_[i] != other.traversal_path()[i]) {
                    return false;
                }
            }
            return true;
        }

        template <typename OtherNodePointer, typename OtherReference, typename OtherPointer>
        bool operator!=(const basic_iterator<OtherNodePointer, OtherReference, OtherPointer>& other) const
        {
            return !(*this == other);
        }

        NodePointer root_node() const noexcept
        {
            return root_;
        }

        const std::vector<NodePointer>& traversal_path() const noexcept
        {
            return path_;
        }

    private:
        void descend_left(NodePointer node)
        {
            while (node) {
                path_.push_back(node);
                node = node->left_.get();
            }
        }

        void descend_right(NodePointer node)
        {
            while (node) {
                path_.push_back(node);
                node = node->right_.get();
            }
        }

        void ascend_to_left_parent()
        {
            while (path_.size() > 1) {
                NodePointer child = path_.back();
                NodePointer parent = path_[path_.size() - 2];
                bool came_from_left = (child == parent->left_.get());
                path_.pop_back();
                if (came_from_left) {
                    return;
                }
            }
            path_.clear();
        }

        void ascend_to_right_parent()
        {
            while (path_.size() > 1) {
                NodePointer child = path_.back();
                NodePointer parent = path_[path_.size() - 2];
                bool came_from_right = (child == parent->right_.get());
                path_.pop_back();
                if (came_from_right) {
                    return;
                }
            }
            path_.clear();
        }

        NodePointer root_ = nullptr;
        std::vector<NodePointer> path_;
    };

    using iterator = basic_iterator<binary_tree*, T&, T*>;
    using const_iterator = basic_iterator<const binary_tree*, const T&, const T*>;

    explicit binary_tree(const T& value)
        : data_(value)
    {
    }

    binary_tree(const binary_tree& other)
        : data_(other.data_),
          left_(clone(other.left_)),
          right_(clone(other.right_))
    {
    }

    binary_tree(binary_tree&&) = default;

    binary_tree& operator=(const binary_tree& other)
    {
        if (this != &other) {
            binary_tree copy(other);
            swap(copy);
        }
        return *this;
    }

    binary_tree& operator=(binary_tree&&) = default;

    ~binary_tree() = default;

    void swap(binary_tree& other)
    {
        using std::swap;
        swap(data_, other.data_);
        left_.swap(other.left_);
        right_.swap(other.right_);
    }

    const T& data() const noexcept
    {
        return data_;
    }

    std::unique_ptr<binary_tree>& left() noexcept
    {
        return left_;
    }

    const std::unique_ptr<binary_tree>& left() const noexcept
    {
        return left_;
    }

    std::unique_ptr<binary_tree>& right() noexcept
    {
        return right_;
    }

    const std::unique_ptr<binary_tree>& right() const noexcept
    {
        return right_;
    }

    void insert(const T& value)
    {
        binary_tree* node = this;
        while (true) {
            if (value < node->data_) {
                if (!node->left_) {
                    node->left_ = std::make_unique<binary_tree>(value);
                    return;
                }
                node = node->left_.get();
            } else if (node->data_ < value) {
                if (!node->right_) {
                    node->right_ = std::make_unique<binary_tree>(value);
                    return;
                }
                node = node->right_.get();
            } else {
                if (!node->left_) {
                    node->left_ = std::make_unique<binary_tree>(value);
                    return;
                }
                node = node->left_.get();
            }
        }
    }

    bool contains(const T& value) const
    {
        const binary_tree* node = this;
        while (node) {
            if (value < node->data_) {
                node = node->left_.get();
            } else if (node->data_ < value) {
                node = node->right_.get();
            } else {
                return true;
            }
        }
        return false;
    }

    bool search(const T& value) const
    {
        return contains(value);
    }

    iterator begin()
    {
        return iterator(this, true);
    }

    iterator end()
    {
        return iterator(this, false);
    }

    const_iterator begin() const
    {
        return const_iterator(this, true);
    }

    const_iterator end() const
    {
        return const_iterator(this, false);
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
    static std::unique_ptr<binary_tree> clone(const std::unique_ptr<binary_tree>& node)
    {
        return node ? std::make_unique<binary_tree>(*node) : nullptr;
    }

    T data_;
    std::unique_ptr<binary_tree> left_;
    std::unique_ptr<binary_tree> right_;
};

}  // namespace binary_search_tree

#endif // BINARY_SEARCH_TREE_H

#if !defined(BINARY_SEARCH_TREE_H)
#define BINARY_SEARCH_TREE_H

#include <cstddef>
#include <iterator>
#include <memory>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace binary_search_tree {

template <typename T>
class binary_tree {
 public:
  using value_type = T;
  using size_type = std::size_t;

 private:
  template <bool IsConst>
  class basic_iterator {
    template <bool>
    friend class basic_iterator;

   public:
    using iterator_category = std::forward_iterator_tag;
    using value_type = T;
    using difference_type = std::ptrdiff_t;
    using reference =
        typename std::conditional<IsConst, const T&, T&>::type;
    using pointer =
        typename std::conditional<IsConst, const T*, T*>::type;

    using node_type =
        typename std::conditional<IsConst, const binary_tree,
                                  binary_tree>::type;

    basic_iterator() = default;

    explicit basic_iterator(node_type* root) {
      push_left(root);
    }

    template <bool OtherConst,
              typename std::enable_if<IsConst && !OtherConst, int>::type = 0>
    basic_iterator(const basic_iterator<OtherConst>& other) {
      for (node_type* node : other.stack_) {
        stack_.push_back(node);
      }
    }

    reference operator*() const {
      return stack_.back()->data_;
    }

    pointer operator->() const {
      return &(stack_.back()->data_);
    }

    basic_iterator& operator++() {
      node_type* current = stack_.back();
      stack_.pop_back();
      push_left(current->right_.get());
      return *this;
    }

    basic_iterator operator++(int) {
      basic_iterator previous(*this);
      ++(*this);
      return previous;
    }

    bool operator==(const basic_iterator& other) const {
      return stack_ == other.stack_;
    }

    bool operator!=(const basic_iterator& other) const {
      return !(*this == other);
    }

   private:
    void push_left(node_type* node) {
      while (node != nullptr) {
        stack_.push_back(node);
        node = node->left_.get();
      }
    }

    std::vector<node_type*> stack_;
  };

 public:
  using iterator = basic_iterator<false>;
  using const_iterator = basic_iterator<true>;
  using node_ptr = std::unique_ptr<binary_tree<T>>;

  explicit binary_tree(const T& data) : data_(data) {
  }

  explicit binary_tree(T&& data) : data_(std::move(data)) {
  }

  binary_tree(const binary_tree&) = delete;
  binary_tree& operator=(const binary_tree&) = delete;
  binary_tree(binary_tree&&) = default;
  binary_tree& operator=(binary_tree&&) = default;

  T& data() {
    return data_;
  }

  const T& data() const {
    return data_;
  }

  node_ptr& left() {
    return left_;
  }

  const node_ptr& left() const {
    return left_;
  }

  node_ptr& right() {
    return right_;
  }

  const node_ptr& right() const {
    return right_;
  }

  void insert(const T& value) {
    if (!(data_ < value)) {
      if (left_) {
        left_->insert(value);
      } else {
        left_.reset(new binary_tree(value));
      }
    } else {
      if (right_) {
        right_->insert(value);
      } else {
        right_.reset(new binary_tree(value));
      }
    }
  }

  void insert(T&& value) {
    if (!(data_ < value)) {
      if (left_) {
        left_->insert(std::move(value));
      } else {
        left_.reset(new binary_tree(std::move(value)));
      }
    } else {
      if (right_) {
        right_->insert(std::move(value));
      } else {
        right_.reset(new binary_tree(std::move(value)));
      }
    }
  }

  iterator begin() {
    return iterator(this);
  }

  iterator end() {
    return iterator();
  }

  const_iterator begin() const {
    return const_iterator(this);
  }

  const_iterator end() const {
    return const_iterator();
  }

  const_iterator cbegin() const {
    return begin();
  }

  const_iterator cend() const {
    return end();
  }

 private:
  T data_;
  node_ptr left_;
  node_ptr right_;
};

}  // namespace binary_search_tree

#endif  // BINARY_SEARCH_TREE_H

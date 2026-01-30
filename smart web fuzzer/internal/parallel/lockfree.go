// Package parallel provides lock-free data structures.
package parallel

import (
	"sync/atomic"
	"unsafe"
)

// LockFreeQueue is a lock-free FIFO queue
type LockFreeQueue struct {
	head unsafe.Pointer
	tail unsafe.Pointer
	len  int64
}

type queueNode struct {
	value interface{}
	next  unsafe.Pointer
}

// NewLockFreeQueue creates a new lock-free queue
func NewLockFreeQueue() *LockFreeQueue {
	node := &queueNode{}
	ptr := unsafe.Pointer(node)
	return &LockFreeQueue{
		head: ptr,
		tail: ptr,
	}
}

// Enqueue adds an item to the queue
func (q *LockFreeQueue) Enqueue(value interface{}) {
	node := &queueNode{value: value}
	nodePtr := unsafe.Pointer(node)

	for {
		tail := atomic.LoadPointer(&q.tail)
		tailNode := (*queueNode)(tail)
		next := atomic.LoadPointer(&tailNode.next)

		if tail == atomic.LoadPointer(&q.tail) {
			if next == nil {
				if atomic.CompareAndSwapPointer(&tailNode.next, nil, nodePtr) {
					atomic.CompareAndSwapPointer(&q.tail, tail, nodePtr)
					atomic.AddInt64(&q.len, 1)
					return
				}
			} else {
				atomic.CompareAndSwapPointer(&q.tail, tail, next)
			}
		}
	}
}

// Dequeue removes and returns an item from the queue
func (q *LockFreeQueue) Dequeue() (interface{}, bool) {
	for {
		head := atomic.LoadPointer(&q.head)
		tail := atomic.LoadPointer(&q.tail)
		headNode := (*queueNode)(head)
		next := atomic.LoadPointer(&headNode.next)

		if head == atomic.LoadPointer(&q.head) {
			if head == tail {
				if next == nil {
					return nil, false
				}
				atomic.CompareAndSwapPointer(&q.tail, tail, next)
			} else {
				nextNode := (*queueNode)(next)
				value := nextNode.value
				if atomic.CompareAndSwapPointer(&q.head, head, next) {
					atomic.AddInt64(&q.len, -1)
					return value, true
				}
			}
		}
	}
}

// Len returns the approximate length of the queue
func (q *LockFreeQueue) Len() int64 {
	return atomic.LoadInt64(&q.len)
}

// IsEmpty returns true if the queue is empty
func (q *LockFreeQueue) IsEmpty() bool {
	return q.Len() == 0
}

// LockFreeStack is a lock-free LIFO stack
type LockFreeStack struct {
	top unsafe.Pointer
	len int64
}

type stackNode struct {
	value interface{}
	next  unsafe.Pointer
}

// NewLockFreeStack creates a new lock-free stack
func NewLockFreeStack() *LockFreeStack {
	return &LockFreeStack{}
}

// Push adds an item to the stack
func (s *LockFreeStack) Push(value interface{}) {
	node := &stackNode{value: value}
	nodePtr := unsafe.Pointer(node)

	for {
		top := atomic.LoadPointer(&s.top)
		node.next = top
		if atomic.CompareAndSwapPointer(&s.top, top, nodePtr) {
			atomic.AddInt64(&s.len, 1)
			return
		}
	}
}

// Pop removes and returns an item from the stack
func (s *LockFreeStack) Pop() (interface{}, bool) {
	for {
		top := atomic.LoadPointer(&s.top)
		if top == nil {
			return nil, false
		}

		topNode := (*stackNode)(top)
		next := topNode.next
		if atomic.CompareAndSwapPointer(&s.top, top, next) {
			atomic.AddInt64(&s.len, -1)
			return topNode.value, true
		}
	}
}

// Len returns the approximate length of the stack
func (s *LockFreeStack) Len() int64 {
	return atomic.LoadInt64(&s.len)
}

// IsEmpty returns true if the stack is empty
func (s *LockFreeStack) IsEmpty() bool {
	return s.Len() == 0
}

// AtomicCounter provides an atomic counter
type AtomicCounter struct {
	value int64
}

// NewAtomicCounter creates a new atomic counter
func NewAtomicCounter(initial int64) *AtomicCounter {
	return &AtomicCounter{value: initial}
}

// Inc increments the counter
func (c *AtomicCounter) Inc() int64 {
	return atomic.AddInt64(&c.value, 1)
}

// Dec decrements the counter
func (c *AtomicCounter) Dec() int64 {
	return atomic.AddInt64(&c.value, -1)
}

// Add adds a value to the counter
func (c *AtomicCounter) Add(delta int64) int64 {
	return atomic.AddInt64(&c.value, delta)
}

// Get returns the current value
func (c *AtomicCounter) Get() int64 {
	return atomic.LoadInt64(&c.value)
}

// Set sets the value
func (c *AtomicCounter) Set(value int64) {
	atomic.StoreInt64(&c.value, value)
}

// CompareAndSwap performs a CAS operation
func (c *AtomicCounter) CompareAndSwap(old, new int64) bool {
	return atomic.CompareAndSwapInt64(&c.value, old, new)
}

// AtomicFlag provides an atomic boolean flag
type AtomicFlag struct {
	value int32
}

// NewAtomicFlag creates a new atomic flag
func NewAtomicFlag(initial bool) *AtomicFlag {
	f := &AtomicFlag{}
	if initial {
		f.Set()
	}
	return f
}

// Set sets the flag to true
func (f *AtomicFlag) Set() {
	atomic.StoreInt32(&f.value, 1)
}

// Clear sets the flag to false
func (f *AtomicFlag) Clear() {
	atomic.StoreInt32(&f.value, 0)
}

// IsSet returns true if the flag is set
func (f *AtomicFlag) IsSet() bool {
	return atomic.LoadInt32(&f.value) == 1
}

// Toggle toggles the flag and returns the new value
func (f *AtomicFlag) Toggle() bool {
	for {
		old := atomic.LoadInt32(&f.value)
		newVal := int32(1)
		if old == 1 {
			newVal = 0
		}
		if atomic.CompareAndSwapInt32(&f.value, old, newVal) {
			return newVal == 1
		}
	}
}

// AtomicValue provides atomic access to arbitrary values
type AtomicValue struct {
	v atomic.Value
}

// NewAtomicValue creates a new atomic value
func NewAtomicValue(initial interface{}) *AtomicValue {
	av := &AtomicValue{}
	if initial != nil {
		av.Store(initial)
	}
	return av
}

// Store stores a value
func (av *AtomicValue) Store(value interface{}) {
	av.v.Store(value)
}

// Load loads the value
func (av *AtomicValue) Load() interface{} {
	return av.v.Load()
}

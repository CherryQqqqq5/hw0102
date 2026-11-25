#include "gigasecond.h"

namespace gigasecond {

namespace {

const boost::posix_time::seconds kGigasecond(1000000000L);

}  // namespace

boost::posix_time::ptime advance(const boost::posix_time::ptime& start) {
    return start + kGigasecond;
}

}  // namespace gigasecond

/** Time-of-day greeting shared by the research list and the incubator. */
export const greeting = (hour = new Date().getHours()) => hour < 11 ? "早上好" : hour < 18 ? "下午好" : "晚上好";

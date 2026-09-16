import { handle } from "hono/vercel";
import { app } from "../server/index.ts";

export default handle(app);
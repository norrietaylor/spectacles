// Edition-2024 `let`-chain (`if let ... && ...`) in deliberately non-canonical
// formatting: irregular spacing around `&&` and operators, and over-indented
// body. rustfmt must both parse it (a let-chain only parses under edition
// 2024) and normalize it. See scripts/test-fmt-letchain.sh and issue #163.
pub fn pick(opt: Option<i32>, flag: bool) -> i32 {
    if let Some(x) = opt &&  flag&&x>0    {
            x
    } else {
        0
    }
}

// Regression test: a previous tabs.tsx wrapped Tabs.Root with
// `flex gap-2 data-horizontal:flex-col`. The `data-horizontal:` modifier
// never matched Radix's `data-orientation="horizontal"` attribute, so the
// root collapsed to `flex` (= flex-row), placing CardHeader and CardContent
// side-by-side and overlapping the table. This test asserts CardHeader
// renders before CardContent in DOM order with a parent that does NOT
// force flex-row.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

describe("Tabs inside Card", () => {
  it("renders CardHeader above CardContent (block stacking)", () => {
    render(
      <Card>
        <Tabs defaultValue="a">
          <CardHeader>
            <CardTitle>Personas</CardTitle>
            <TabsList>
              <TabsTrigger value="a">Miembros</TabsTrigger>
              <TabsTrigger value="b">Invitaciones</TabsTrigger>
            </TabsList>
          </CardHeader>
          <CardContent>
            <TabsContent value="a">
              <div data-testid="table">table-here</div>
            </TabsContent>
          </CardContent>
        </Tabs>
      </Card>,
    );

    // Radix Tabs.Root renders with role="presentation"? Actually no — Tabs.Root
    // is a plain div. We find it via the orientation data attribute that Radix
    // always sets.
    const tabsRoot = document.querySelector(
      'div[data-orientation="horizontal"]',
    ) as HTMLElement | null;
    expect(tabsRoot).not.toBeNull();

    // Tabs root must not force a row layout. We accept any of: no flex,
    // explicit block, or flex-col. The historical bug applied bare `flex`.
    const cls = tabsRoot!.className;
    const looksLikeRowFlex = /\bflex\b/.test(cls) && !/\bflex-col\b/.test(cls);
    expect(looksLikeRowFlex).toBe(false);

    // CardHeader (containing Personas) and CardContent (containing table)
    // must both be direct children of Tabs root, with header before content.
    const title = screen.getByText("Personas");
    const table = screen.getByTestId("table");
    const headerChild = Array.from(tabsRoot!.children).find((c) => c.contains(title)) as
      | HTMLElement
      | undefined;
    const contentChild = Array.from(tabsRoot!.children).find((c) => c.contains(table)) as
      | HTMLElement
      | undefined;
    expect(headerChild).toBeDefined();
    expect(contentChild).toBeDefined();
    expect(
      headerChild!.compareDocumentPosition(contentChild!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
